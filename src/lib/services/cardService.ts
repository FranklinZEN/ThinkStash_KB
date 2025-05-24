import { Prisma, KnowledgeCard } from '@prisma/client';
import prisma from '@/lib/prisma';
import {
  StandardDocument,
  isImageBlock,
  // MyAppImageBlockProps, // Removed unused import
} from '@/types/editorTypes';
import {
  uploadFile as uploadFileToGCS,
  deleteFile as deleteFileFromGCS,
} from '@/lib/gcs';
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
): Promise<string[]> {
  const activeImageRecordIds: string[] = [];

  for (let i = 0; i < blocks.length; i++) {
    const currentBlock = blocks[i];

    if (isImageBlock(currentBlock)) {
      const imageProps = currentBlock.props;
      const originalUrl = imageProps.url;
      const captionToStore = imageProps.caption;

      let appServedUrlToStore = originalUrl || '';

      if (
        typeof originalUrl === 'string' &&
        originalUrl.startsWith('data:image')
      ) {
        try {
          console.log(
            `[cardService] (_processAndLinkImages) Processing data: URL for card context ${cardId}`,
          );
          const parts = originalUrl.split(',');
          if (parts.length < 2) {
            console.warn(
              '[cardService] (_processAndLinkImages) Invalid data: URL format (missing comma). Skipping.',
              originalUrl.substring(0, 80) + '...',
            );
            continue;
          }
          const meta = parts[0];
          const base64Data = parts[1];
          const contentTypeMatch = meta.match(/data:(image\/[^;]+);base64/);
          if (!contentTypeMatch || !contentTypeMatch[1]) {
            console.warn(
              '[cardService] (_processAndLinkImages) Could not determine content type from data: URL. Skipping.',
              meta,
            );
            continue;
          }
          const contentType = contentTypeMatch[1];
          if (!GCS_ALLOWED_MIME_TYPES.includes(contentType.toLowerCase())) {
            console.warn(
              `[cardService] (_processAndLinkImages) Unsupported content type from data: URL: ${contentType}. Skipping.`,
            );
            continue;
          }
          const buffer = Buffer.from(base64Data, 'base64');
          if (buffer.length > GCS_MAX_SIZE_BYTES) {
            console.warn(
              `[cardService] (_processAndLinkImages) Image from data: URL exceeds size limit. Size: ${buffer.length}bytes. Max: ${GCS_MAX_SIZE_BYTES}bytes. Skipping.`,
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
            },
          });
          const actualAppServedUrl = `/api/images/serve/${newImageRecord.id}`;
          await prisma.imageRecord.update({
            where: { id: newImageRecord.id },
            data: { appServedUrl: actualAppServedUrl },
          });
          appServedUrlToStore = actualAppServedUrl;
          activeImageRecordIds.push(newImageRecord.id);
          console.log(
            `[cardService] (_processAndLinkImages) Successfully processed data: URL. New appServedUrl: ${actualAppServedUrl}. ImageRecord ID: ${newImageRecord.id}`,
          );
        } catch (error) {
          console.error(
            `[cardService] (_processAndLinkImages) Failed to process data: URL for card context ${cardId}:`,
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
            select: { id: true },
          });
          if (imageRecord) {
            if (!activeImageRecordIds.includes(potentialId)) {
              activeImageRecordIds.push(potentialId);
            }
          } else {
            console.warn(
              `[cardService] (_processAndLinkImages) appServedUrl ${originalUrl} in card context ${cardId} does not correspond to a valid/owned ImageRecord. It will be preserved as is in content.`,
            );
          }
        }
      }

      blocks[i] = {
        ...currentBlock,
        props: {
          ...imageProps,
          url: appServedUrlToStore,
          caption: captionToStore || '',
        },
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
        const childImageIds = await _processAndLinkImages(
          blockToProcessForChildren.children as StandardDocument,
          cardId,
          userId,
        );
        childImageIds.forEach((id) => {
          if (!activeImageRecordIds.includes(id)) {
            activeImageRecordIds.push(id);
          }
        });
      }
    }
  }
  return activeImageRecordIds;
}

// New exported function to handle image associations
export async function handleCardImageAssociations(
  content: Prisma.JsonValue | undefined | null,
  cardId: string,
  userId: string,
): Promise<{
  processedContent: Prisma.JsonValue | undefined | null;
  activeImageRecordIds: string[];
}> {
  if (!content || !Array.isArray(content) || content.length === 0) {
    return { processedContent: content, activeImageRecordIds: [] };
  }

  let mutableContent: StandardDocument;
  try {
    mutableContent = JSON.parse(JSON.stringify(content)) as StandardDocument;
  } catch (cloneError) {
    console.error(
      '[cardService] (handleCardImageAssociations) Failed to clone content for image processing. Returning original content.',
      cloneError,
    );
    return { processedContent: content, activeImageRecordIds: [] };
  }

  const activeImageRecordIds = await _processAndLinkImages(
    mutableContent,
    cardId,
    userId,
  );

  return {
    processedContent: mutableContent as unknown as Prisma.JsonValue,
    activeImageRecordIds,
  };
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
    // 1. Verify card ownership and fetch existing card (needed for pre-update state)
    const existingCardForOwnershipCheck = await prisma.knowledgeCard.findUnique(
      {
        where: { id: cardId, userId: userId },
        select: { id: true }, // Only need ID for ownership check initially
      },
    );
    if (!existingCardForOwnershipCheck) {
      return {
        success: false,
        error: 'Card not found or not owned by user',
        status: 404,
      };
    }

    // Fetch all ImageRecords currently linked to this card by this user
    // These are candidates for becoming orphans if not present in the updated content
    const imageRecordsInitiallyLinkedToCard = await prisma.imageRecord.findMany(
      {
        where: {
          knowledgeCardId: cardId,
          userId: userId, // Ensure we only consider images owned by the user associated with this card
        },
        select: { id: true, gcsPath: true },
      },
    );
    // Defensively handle if findMany could somehow not return an array
    const initialImageRecordIds = imageRecordsInitiallyLinkedToCard
      ? imageRecordsInitiallyLinkedToCard.map((img) => img.id)
      : [];

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

    // Process content:
    // - new data: URLs are converted to ImageRecords (unlinked initially)
    // - existing /api/images/serve/ URLs are identified
    // - The content JSON is updated with appServedUrls
    // - Returns a list of ImageRecord IDs that are present in the *new* content
    let processedContent = data.content;
    const contentWasActuallyInRequest = data.content !== undefined;
    let activeImageRecordIdsInNewContent: string[] = [];

    if (contentWasActuallyInRequest && data.content) {
      const imageAssociationResult = await handleCardImageAssociations(
        data.content,
        cardId,
        userId,
      );
      processedContent = imageAssociationResult.processedContent;
      activeImageRecordIdsInNewContent =
        imageAssociationResult.activeImageRecordIds;
      console.log(
        `[cardService] (updateCardLogic) Content processed. Found ${activeImageRecordIdsInNewContent.length} active image IDs in new content for card ${cardId}.`,
      );
    } else if (!contentWasActuallyInRequest) {
      // If content is not part of the request, then all initially linked images are still considered active for this card
      activeImageRecordIdsInNewContent = [...initialImageRecordIds];
      console.log(
        `[cardService] (updateCardLogic) Content not in update request. Assuming all ${initialImageRecordIds.length} initially linked images are still active for card ${cardId}.`,
      );
    }

    // 3. Construct Prisma update payload for the KnowledgeCard itself
    const updatePayload: Prisma.KnowledgeCardUpdateInput = {};
    if (data.title !== undefined) updatePayload.title = data.title;

    if (contentWasActuallyInRequest) {
      if (processedContent === null || processedContent === undefined) {
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
      updatePayload.tags = {
        set: [],
        connectOrCreate: uniqueTrimmedTags.map((tagName: string) => ({
          where: { name: tagName },
          create: { name: tagName },
        })),
      };
    }

    // Perform the actual KnowledgeCard update
    // Do this before orphan processing to ensure the card update itself is successful
    if (Object.keys(updatePayload).length > 0) {
      await prisma.knowledgeCard.update({
        where: { id: cardId, userId: userId }, // Ensure userId for security
        data: updatePayload,
      });
      console.log(
        `[cardService] (updateCardLogic) KnowledgeCard ${cardId} main fields updated.`,
      );
    } else if (!contentWasActuallyInRequest) {
      // No direct card fields to update, and content wasn't in request, so no further image processing needed here
      // The card state regarding images effectively remains unchanged.
      console.log(
        `[cardService] (updateCardLogic) No direct card fields to update for card ${cardId} and content not in request.`,
      );
    }

    // 4. Manage ImageRecord associations and orphan cleanup
    // This section runs regardless of whether content was in the request,
    // as activeImageRecordIdsInNewContent is populated based on that.

    // Link all ImageRecords that are active in the new content to this card
    if (activeImageRecordIdsInNewContent.length > 0) {
      await prisma.imageRecord.updateMany({
        where: {
          id: { in: activeImageRecordIdsInNewContent },
          userId: userId, // Ensure user owns these image records
        },
        data: { knowledgeCardId: cardId },
      });
      console.log(
        `[cardService] (updateCardLogic) Linked/Re-linked ${activeImageRecordIdsInNewContent.length} active images to card ${cardId}. IDs: ${activeImageRecordIdsInNewContent.join(', ')}`,
      );
    }

    // Identify ImageRecords that were linked before but are NOT in the new active set for this card
    const potentiallyOrphanedIds = initialImageRecordIds.filter(
      (id) => !activeImageRecordIdsInNewContent.includes(id),
    );

    if (potentiallyOrphanedIds.length > 0) {
      console.log(
        `[cardService] (updateCardLogic) Card ${cardId} has ${potentiallyOrphanedIds.length} potentially orphaned ImageRecords. IDs: ${potentiallyOrphanedIds.join(', ')}`,
      );

      // First, ensure these images are unlinked from the *current* card
      // This is crucial if an image was moved from this card to another by the user in a complex operation.
      // We only set knowledgeCardId to null if it's currently this cardId.
      await prisma.imageRecord.updateMany({
        where: {
          id: { in: potentiallyOrphanedIds },
          userId: userId,
          knowledgeCardId: cardId, // Important: only update if still linked to THIS card
        },
        data: { knowledgeCardId: null },
      });
      console.log(
        `[cardService] (updateCardLogic) Unlinked ${potentiallyOrphanedIds.length} images from card ${cardId} (set knowledgeCardId to null).`,
      );

      for (const orphanId of potentiallyOrphanedIds) {
        const imageRecordDetails = imageRecordsInitiallyLinkedToCard.find(
          (img) => img.id === orphanId,
        );
        if (!imageRecordDetails) continue; // Should not happen

        // Check if this ImageRecord is now linked to ANY KnowledgeCard by this user
        const isStillLinkedToAnyCardByOwner =
          await prisma.imageRecord.findFirst({
            where: {
              id: orphanId,
              userId: userId,
              knowledgeCardId: { not: null }, // Check if it's linked to *any* card
            },
            select: { id: true, knowledgeCardId: true },
          });

        if (!isStillLinkedToAnyCardByOwner) {
          // Truly orphaned: Delete GCS file and then the ImageRecord
          console.log(
            `[cardService] (updateCardLogic) ImageRecord ${orphanId} is truly orphaned. Deleting GCS file and DB record for card ${cardId} context.`,
          );
          if (imageRecordDetails.gcsPath) {
            try {
              await deleteFileFromGCS(imageRecordDetails.gcsPath);
              console.log(
                `[cardService] (updateCardLogic) Successfully deleted GCS file: ${imageRecordDetails.gcsPath} for orphaned ImageRecord: ${orphanId}`,
              );
            } catch (gcsError) {
              console.error(
                `[cardService] (updateCardLogic) Failed to delete GCS file: ${imageRecordDetails.gcsPath} for orphaned ImageRecord: ${orphanId}. Error:`,
                gcsError,
              );
              // Log and continue, as per robust handling principle. DB record will still be deleted.
            }
          }
          await prisma.imageRecord.delete({
            where: { id: orphanId, userId: userId }, // Ensure user ownership for delete
          });
          console.log(
            `[cardService] (updateCardLogic) Successfully deleted orphaned ImageRecord ${orphanId} from DB.`,
          );
        } else {
          console.log(
            `[cardService] (updateCardLogic) ImageRecord ${orphanId} was unlinked from card ${cardId} but is still linked to another card (${isStillLinkedToAnyCardByOwner.knowledgeCardId}) by user ${userId}. No deletion needed.`,
          );
        }
      }
    } else {
      console.log(
        `[cardService] (updateCardLogic) No images were unlinked from card ${cardId} that were previously linked.`,
      );
    }

    // 5. Re-fetch the card to return the latest state with all associations
    const fullyUpdatedCard = await prisma.knowledgeCard.findUnique({
      where: { id: cardId, userId: userId }, // Re-check userId for security on final fetch
      include: { tags: true, folder: true },
    });

    if (!fullyUpdatedCard) {
      // This case should ideally not be reached if update was successful
      console.error(
        `[cardService] (updateCardLogic) CRITICAL: Failed to re-fetch card ${cardId} after update and orphan processing.`,
      );
      return {
        success: false,
        error: 'Failed to retrieve card after update operations.',
        status: 500,
      };
    }

    return { success: true, data: fullyUpdatedCard, status: 200 };
  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      if (error.code === 'P2003' || error.code === 'P2025') {
        // Foreign key constraint or record not found
        return {
          success: false,
          error:
            'Invalid related data (e.g., folder ID or tag issue, or record to update/delete not found).',
          status: 400,
          details: error.message,
        };
      }
    }
    console.error(
      '[cardService] (updateCardLogic) Failed to update card:',
      error,
    );
    return {
      success: false,
      error: 'Failed to update card.',
      details: error instanceof Error ? error.message : String(error),
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

    // 2. Get ImageRecords associated with the card to delete their GCS files
    const imageRecordsToDelete = await prisma.imageRecord.findMany({
      where: { knowledgeCardId: cardId },
      select: { gcsPath: true, id: true },
    });

    // 3. Delete files from GCS
    // Defensively handle if findMany could somehow not return an array
    if (imageRecordsToDelete && imageRecordsToDelete.length > 0) {
      console.log(
        `[cardService] Found ${imageRecordsToDelete.length} image(s) in GCS to delete for card ${cardId}.`,
      );
      for (const record of imageRecordsToDelete) {
        if (record.gcsPath) {
          try {
            await deleteFileFromGCS(record.gcsPath);
            console.log(
              `[cardService] Successfully deleted GCS file: ${record.gcsPath} for ImageRecord: ${record.id}`,
            );
          } catch (gcsError) {
            console.error(
              `[cardService] Failed to delete GCS file: ${record.gcsPath} for ImageRecord: ${record.id}. Error:`,
              gcsError,
            );
          }
        } else {
          console.warn(
            `[cardService] ImageRecord ${record.id} for card ${cardId} has no gcsPath. Skipping GCS deletion for this record.`,
          );
        }
      }
    }

    // 4. Delete the card (onDelete: Cascade for ImageRecord is handled by Prisma schema)
    const deletedCard = await prisma.knowledgeCard.delete({
      where: { id: cardId },
    });

    // Note: Deletion of GCS files for ImageRecords associated with this card
    // is now handled above.

    return { success: true, data: deletedCard, status: 200 };
  } catch (error) {
    console.error('[cardService] Failed to delete card:', error);
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      return {
        success: false,
        error: 'Failed to delete card from database.',
        details: error.message,
        status: 500,
      };
    }
    return {
      success: false,
      error: 'Failed to delete card.',
      details: error instanceof Error ? error.message : String(error),
      status: 500,
    };
  }
}
