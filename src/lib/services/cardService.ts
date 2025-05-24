import { Prisma, KnowledgeCard } from '@prisma/client';
import prisma from '@/lib/prisma';
import {
  StandardDocument,
  isImageBlock,
  MyAppImageBlockProps,
} from '@/types/editorTypes';
import { uploadFile as uploadFileToGCS } from '@/lib/gcs';
import { v4 as uuidv4 } from 'uuid'; // For generating filenames

// --- Interfaces for Prisma Subset ---
// export interface CardServicePrismaSubset { ... }

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

const GCS_ALLOWED_MIME_TYPES = [
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
];
const GCS_MAX_SIZE_BYTES = 5 * 1024 * 1024; // 5MB

// Renamed to _processAndLinkImages and logic significantly updated
async function _processAndLinkImages(
  blocks: StandardDocument,
  cardId: string,
  userId: string,
): Promise<void> {
  const imageRecordIdsToLink: string[] = [];

  for (let i = 0; i < blocks.length; i++) {
    const currentBlock = blocks[i];

    if (isImageBlock(currentBlock)) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const defaultImageProps = currentBlock.props as any;
      const originalUrl = defaultImageProps.url;
      let appServedUrlToStore = originalUrl || '';
      const captionToStore = defaultImageProps.caption;

      if (
        typeof originalUrl === 'string' &&
        originalUrl.startsWith('data:image')
      ) {
        try {
          console.log(`[cardService] Processing data: URL for card ${cardId}`);
          const parts = originalUrl.split(',');
          if (parts.length < 2) {
            console.warn(
              '[cardService] Invalid data: URL format (missing comma). Skipping.',
              originalUrl.substring(0, 80) + '...',
            );
            continue;
          }
          const meta = parts[0];
          const base64Data = parts[1];
          const contentTypeMatch = meta.match(/data:(image\/[^;]+);base64/);
          if (!contentTypeMatch || !contentTypeMatch[1]) {
            console.warn(
              '[cardService] Could not determine content type from data: URL. Skipping.',
              meta,
            );
            continue;
          }
          const contentType = contentTypeMatch[1];
          if (!GCS_ALLOWED_MIME_TYPES.includes(contentType.toLowerCase())) {
            console.warn(
              `[cardService] Unsupported content type from data: URL: ${contentType}. Skipping.`,
            );
            continue;
          }
          const buffer = Buffer.from(base64Data, 'base64');
          if (buffer.length > GCS_MAX_SIZE_BYTES) {
            console.warn(
              `[cardService] Image from data: URL exceeds size limit. Size: ${buffer.length}bytes. Max: ${GCS_MAX_SIZE_BYTES}bytes. Skipping.`,
            );
            continue;
          }
          const fileExtension = contentType.split('/')[1] || 'png';
          const gcsOriginalFilename = `pasted-${uuidv4()}.${fileExtension}`;
          const gcsUploadResult = await uploadFileToGCS(
            buffer,
            gcsOriginalFilename,
            contentType,
          );
          const newImageRecord = await prisma.imageRecord.create({
            data: {
              userId,
              gcsPath: gcsUploadResult.filename,
              contentType,
              originalFilename: gcsOriginalFilename,
              size: buffer.length,
              appServedUrl: '',
              knowledgeCardId: cardId,
            },
          });
          const actualAppServedUrl = `/api/images/serve/${newImageRecord.id}`;
          await prisma.imageRecord.update({
            where: { id: newImageRecord.id },
            data: { appServedUrl: actualAppServedUrl },
          });
          appServedUrlToStore = actualAppServedUrl;
          console.log(
            `[cardService] Successfully processed data: URL. New appServedUrl: ${actualAppServedUrl}`,
          );
        } catch (error) {
          console.error(
            `[cardService] Failed to process data: URL for card ${cardId}:`,
            error instanceof Error ? error.message : error,
            originalUrl.substring(0, 80) + '...',
          );
        }
      } else if (
        typeof originalUrl === 'string' &&
        originalUrl.startsWith('/api/images/serve/')
      ) {
        const urlParts = originalUrl.split('/');
        const potentialId = urlParts[urlParts.length - 1];
        const isCuidLike =
          potentialId &&
          potentialId.length === 25 &&
          potentialId.startsWith('c');
        if (isCuidLike) {
          const imageRecord = await prisma.imageRecord.findFirst({
            where: { id: potentialId, userId: userId },
            select: { id: true, knowledgeCardId: true },
          });
          if (imageRecord && imageRecord.knowledgeCardId !== cardId) {
            if (!imageRecordIdsToLink.includes(potentialId)) {
              imageRecordIdsToLink.push(potentialId);
            }
          }
        }
      }

      const minimalProps: MyAppImageBlockProps = { url: appServedUrlToStore };
      if (captionToStore) {
        minimalProps.caption = captionToStore;
      }

      blocks[i] = {
        ...currentBlock,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        props: minimalProps as any,
      };
    }

    const blockToProcessForChildren = blocks[i];
    if (
      blockToProcessForChildren.children &&
      Array.isArray(blockToProcessForChildren.children) &&
      blockToProcessForChildren.children.length > 0
    ) {
      const childrenAreBlocks = blockToProcessForChildren.children.every(
        (child) =>
          typeof child === 'object' && child !== null && 'type' in child,
      );
      if (childrenAreBlocks) {
        await _processAndLinkImages(
          blockToProcessForChildren.children as StandardDocument,
          cardId,
          userId,
        );
      }
    }
  }

  if (imageRecordIdsToLink.length > 0) {
    try {
      await prisma.imageRecord.updateMany({
        where: { id: { in: imageRecordIdsToLink }, userId: userId },
        data: { knowledgeCardId: cardId },
      });
      console.log(
        `[cardService] Linked ${imageRecordIdsToLink.length} existing appServed images to card ${cardId}`,
      );
    } catch (dbError) {
      console.error(
        `[cardService] Error linking existing appServed images to card ${cardId} in DB:`,
        dbError,
      );
    }
  }
}

// New exported function to handle image associations
export async function handleCardImageAssociations(
  content: Prisma.JsonValue | undefined | null,
  cardId: string,
  userId: string,
): Promise<Prisma.JsonValue | undefined | null> {
  if (!content || !Array.isArray(content) || content.length === 0) {
    return content;
  }

  let mutableContent: StandardDocument;
  try {
    mutableContent = JSON.parse(JSON.stringify(content)) as StandardDocument;
  } catch (cloneError) {
    console.error(
      '[cardService] Failed to clone content for image processing. Returning original content.',
      cloneError,
    );
    return content;
  }

  await _processAndLinkImages(mutableContent, cardId, userId);

  return mutableContent as unknown as Prisma.JsonValue;
}

// --- GET Card Logic ---
export async function getCardLogic(
  cardId: string,
  userId: string,
): Promise<
  ServiceResult<
    Prisma.KnowledgeCardGetPayload<{ include: { folder: true; tags: true } }>
  >
> {
  try {
    const card = await prisma.knowledgeCard.findUnique({
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
  data: UpdateCardData, // This is validatedBody from the route
): Promise<
  ServiceResult<
    Prisma.KnowledgeCardGetPayload<{ include: { folder: true; tags: true } }>
  >
> {
  try {
    // 1. Verify card ownership
    const existingCard = await prisma.knowledgeCard.findUnique({
      where: { id: cardId, userId: userId },
      select: { id: true },
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
      const targetFolder = await prisma.folder.findUnique({
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

    // Process content for image associations *before* constructing the main update payload
    let processedContent = data.content;
    const contentWasActuallyInRequest = data.content !== undefined;

    if (contentWasActuallyInRequest && data.content) {
      const modifiedContent = await handleCardImageAssociations(
        data.content,
        cardId,
        userId,
      );
      processedContent = modifiedContent;
      console.log(
        `[cardService] Content processed by handleCardImageAssociations for card update ${cardId}`,
      );
    }

    // 3. Construct Prisma update payload using processedContent
    const updatePayload: Prisma.KnowledgeCardUpdateInput = {};
    if (data.title !== undefined) updatePayload.title = data.title;

    if (contentWasActuallyInRequest) {
      if (processedContent === null || processedContent === undefined) {
        // Check for undefined if content wasn't in request but processedContent might be undefined
        // If original data.content was explicitly null, and it remained null/undefined after processing, treat as Prisma.JsonNull
        // If content was not in request, processedContent would be undefined, so don't add to payload
        if (data.content === null) {
          updatePayload.content = Prisma.JsonNull;
        }
      } else {
        updatePayload.content = processedContent;
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
      // To truly replace tags, we first disconnect all, then connect/create new ones.
      // If you only want to add/remove specific tags, this logic would be different (e.g., using disconnect/connect arrays based on diffs)
      // For simplicity of replacing all tags as per current structure:
      updatePayload.tags = {
        set: [], // This effectively disconnects all existing tags for the card
        connectOrCreate: uniqueTrimmedTags.map((tagName: string) => ({
          where: { name: tagName },
          create: { name: tagName },
        })),
      };
    }

    if (Object.keys(updatePayload).length === 0) {
      const currentCardData = await getCardLogic(cardId, userId);
      if (currentCardData.success && currentCardData.data) {
        return { ...currentCardData, status: 200, data: currentCardData.data };
      }
      return {
        success: false,
        error:
          'No valid fields provided for update, and failed to refetch card.',
        status: 400,
      };
    }

    await prisma.knowledgeCard.update({
      where: { id: cardId, userId: userId },
      data: updatePayload,
      include: { tags: true, folder: true },
    });

    // Re-fetch the card to ensure all associations and updates are reflected in the returned data
    // This is important because `updatedCard` from the update operation might not reflect
    // nested relation changes perfectly or all computed fields if any.
    const fullyUpdatedCard = await prisma.knowledgeCard.findUnique({
      where: { id: cardId }, // userId check not strictly needed again if update succeeded
      include: { tags: true, folder: true },
    });

    if (!fullyUpdatedCard) {
      return {
        success: false,
        error: 'Failed to retrieve card after update.',
        status: 500,
      };
    }

    return { success: true, data: fullyUpdatedCard, status: 200 };
  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      if (error.code === 'P2003' || error.code === 'P2025') {
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
): Promise<ServiceResult<KnowledgeCard>> {
  try {
    // 1. Verify card ownership before deleting
    const existingCard = await prisma.knowledgeCard.findUnique({
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
    const deletedCard = await prisma.knowledgeCard.delete({
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
