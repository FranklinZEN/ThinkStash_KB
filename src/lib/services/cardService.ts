import { Prisma, KnowledgeCard, PrismaClient } from '@prisma/client';
import type { Block } from '@blocknote/core'; // Added for BlockNote type

// --- Interfaces for Prisma Subset ---
export interface CardServicePrismaSubset {
  knowledgeCard: {
    findUnique: PrismaClient['knowledgeCard']['findUnique'];
    update: PrismaClient['knowledgeCard']['update'];
    delete: PrismaClient['knowledgeCard']['delete'];
  };
  folder: {
    findUnique: PrismaClient['folder']['findUnique'];
  };
  // Tag model might be needed if create/connect logic for tags is complex, but connectOrCreate handles it.
}

// --- Service Result Interface (can be shared) ---
export interface ServiceResult<T> {
  success: boolean;
  data?: T;
  error?: string;
  details?: unknown;
  status?: number;
}

// --- Input DTOs ---
// Using Prisma.KnowledgeCardUpdateInput directly for updateData might be too broad if we want to control fields.
// For now, let's define a more specific one based on UpdateCardSchema from the route.
export interface UpdateCardData {
  title?: string;
  content?: Prisma.JsonValue; // Assuming content is Json
  folderId?: string | null;
  tags?: string[];
}

// Renamed to _linkImagesToCard and will be used by an exported function
async function _linkImagesToCard(
  prisma: PrismaClient,
  content: Prisma.JsonValue | undefined | null,
  cardId: string,
  userId: string,
) {
  if (!content || !Array.isArray(content)) {
    return;
  }

  const imageRecordIdsToUpdate: string[] = [];
  const blocks = content as Block[];

  for (const block of blocks) {
    if (
      block.type === 'image' &&
      block.props &&
      typeof block.props.url === 'string'
    ) {
      const url = block.props.url as string;
      // console.log('[_linkImagesToCard] Processing image block with URL:', url); // Removed log

      const urlParts = url.split('/');
      if (urlParts.length > 0) {
        const potentialId = urlParts[urlParts.length - 1];
        // console.log('[_linkImagesToCard] Extracted potentialId:', potentialId); // Removed log

        const isCuidLike =
          potentialId &&
          potentialId.length === 25 &&
          potentialId.startsWith('c');
        // console.log('[_linkImagesToCard] Is potentialId CUID-like?:', isCuidLike, '(ID:', potentialId, ')'); // Removed log

        if (isCuidLike) {
          const imageRecord = await prisma.imageRecord.findFirst({
            where: { id: potentialId, userId: userId },
            select: { id: true, knowledgeCardId: true },
          });
          // console.log('[_linkImagesToCard] DB query result for ImageRecord:', imageRecord, '(for ID:', potentialId, ')'); // Removed log

          if (imageRecord && imageRecord.knowledgeCardId !== cardId) {
            imageRecordIdsToUpdate.push(potentialId);
          }
        }
      }
    }
    if (block.children && block.children.length > 0) {
      await _linkImagesToCard(
        prisma,
        block.children as unknown as Prisma.JsonValue,
        cardId,
        userId,
      );
    }
  }

  if (imageRecordIdsToUpdate.length > 0) {
    try {
      await prisma.imageRecord.updateMany({
        where: {
          id: { in: imageRecordIdsToUpdate },
          userId: userId,
        },
        data: { knowledgeCardId: cardId },
      });
      // console.log(`[cardService] Linked ${imageRecordIdsToUpdate.length} images to card ${cardId}`); // Optional: keep for info
    } catch (dbError) {
      console.error(
        `[cardService] Error linking images to card ${cardId} in DB:`,
        dbError,
      );
      // Decide if this error should be propagated or just logged
    }
  }
}

// New exported function to handle image associations
export async function handleCardImageAssociations(
  prisma: PrismaClient,
  content: Prisma.JsonValue | undefined | null,
  cardId: string,
  userId: string,
) {
  await _linkImagesToCard(prisma, content, cardId, userId);
}

// --- GET Card Logic ---
export async function getCardLogic(
  cardId: string,
  userId: string,
  prismaInstance: PrismaClient,
): Promise<
  ServiceResult<
    Prisma.KnowledgeCardGetPayload<{ include: { folder: true; tags: true } }>
  >
> {
  try {
    const card = await prismaInstance.knowledgeCard.findUnique({
      where: { id: cardId, userId: userId },
      include: { folder: true, tags: true },
    });

    if (!card) {
      return {
        success: false,
        error: 'Card not found or access denied',
        status: 404,
      };
    }
    return { success: true, data: card, status: 200 };
  } catch (error) {
    console.error('[cardService] Failed to fetch card:', error);
    return { success: false, error: 'Failed to retrieve card.', status: 500 };
  }
}

// --- PUT (Update) Card Logic ---
export async function updateCardLogic(
  cardId: string,
  userId: string,
  data: UpdateCardData,
  prismaInstance: PrismaClient,
): Promise<
  ServiceResult<
    Prisma.KnowledgeCardGetPayload<{ include: { folder: true; tags: true } }>
  >
> {
  try {
    // 1. Verify card ownership (already done in route handler, but good for service to be independent if called elsewhere)
    const existingCard = await prismaInstance.knowledgeCard.findUnique({
      where: { id: cardId, userId: userId },
      select: { id: true }, // Only need to check existence
    });
    if (!existingCard) {
      return {
        success: false,
        error: 'Card not found or not owned by user',
        status: 404,
      };
    }

    // 2. Validate folderId ownership if provided and not null
    if (data.folderId) {
      // if folderId is present and not null
      const targetFolder = await prismaInstance.folder.findUnique({
        where: { id: data.folderId, userId: userId },
        select: { id: true },
      });
      if (!targetFolder) {
        return {
          success: false,
          error: 'Target folder not found or not owned by user',
          status: 400,
        };
      }
    }

    // 3. Construct Prisma update payload
    const updatePayload: Prisma.KnowledgeCardUpdateInput = {};
    if (data.title !== undefined) updatePayload.title = data.title;

    let contentChanged = false; // Flag to see if content was part of the update
    if (data.content !== undefined) {
      contentChanged = true;
      if (data.content === null) {
        updatePayload.content = Prisma.JsonNull; // Use Prisma.JsonNull for explicit null
      } else {
        updatePayload.content = data.content; // For other JsonValue types
      }
    }

    if (data.folderId !== undefined) {
      if (data.folderId === null) {
        updatePayload.folder = { disconnect: true };
      } else {
        updatePayload.folder = { connect: { id: data.folderId } };
      }
    }

    if (data.tags !== undefined) {
      const uniqueTrimmedTags = data.tags
        .map((tag) => tag.trim())
        .filter((tag) => tag.length > 0);
      updatePayload.tags = {
        set: [], // Disconnect all existing tags first
        connectOrCreate: uniqueTrimmedTags.map((tagName: string) => ({
          where: { name: tagName },
          create: { name: tagName },
        })),
      };
    }

    if (Object.keys(updatePayload).length === 0) {
      // This case should ideally be caught by Zod schema in route if .partial().refine was stricter
      // but good to have a service level check if no actual update fields were processed.
      // Re-fetch and return existing card to indicate no change but not an error.
      const currentCard = await getCardLogic(cardId, userId, prismaInstance);
      if (currentCard.success) return { ...currentCard, status: 200 }; // Or a 304 Not Modified like status
      return {
        success: false,
        error:
          'No valid fields provided for update, and failed to refetch card.',
        status: 400,
      };
    }

    const updatedCard = await prismaInstance.knowledgeCard.update({
      where: { id: cardId }, // userId check was done via existingCard check
      data: updatePayload,
      include: { tags: true, folder: true },
    });

    // After successfully updating the card, if content was part of the update, link images
    if (updatedCard && contentChanged && data.content) {
      await handleCardImageAssociations(
        prismaInstance,
        data.content,
        updatedCard.id,
        userId,
      ); // Use the new exported function
    }

    return { success: true, data: updatedCard, status: 200 };
  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      if (error.code === 'P2003' || error.code === 'P2025') {
        // Foreign key constraint or record not found for connect
        return {
          success: false,
          error: 'Invalid related data (e.g., folder ID or tag issue)',
          status: 400,
        };
      }
    }
    console.error('[cardService] Failed to update card:', error);
    return {
      success: false,
      error: 'Failed to update card.',
      details: (error as Error).message,
      status: 500,
    };
  }
}

// --- DELETE Card Logic ---
export async function deleteCardLogic(
  cardId: string,
  userId: string,
  prismaInstance: PrismaClient,
): Promise<ServiceResult<KnowledgeCard>> {
  try {
    // 1. Verify card ownership before deleting
    const existingCard = await prismaInstance.knowledgeCard.findUnique({
      where: { id: cardId, userId: userId },
      select: { id: true }, // Only need to check existence
    });

    if (!existingCard) {
      return {
        success: false,
        error: 'Card not found or not owned by user',
        status: 404,
      };
    }

    // 2. Delete the card (onDelete: Cascade for ImageRecord is handled by Prisma schema)
    const deletedCard = await prismaInstance.knowledgeCard.delete({
      where: { id: cardId },
    });

    // Note: Deletion of GCS files for ImageRecords associated with this card
    // needs to be handled separately, ideally *before* the card and its ImageRecords are cascade-deleted.
    // This service currently doesn't handle GCS cleanup.

    return { success: true, data: deletedCard, status: 200 }; // Or 204 No Content
  } catch (error) {
    console.error('[cardService] Failed to delete card:', error);
    return {
      success: false,
      error: 'Failed to delete card.',
      details: (error as Error).message,
      status: 500,
    };
  }
}
