import { Prisma } from '@prisma/client';
import prisma, { prismaReady } from '@/lib/prisma';
import {
  StandardDocument,
  isImageBlock,
} from '@/types/editorTypes';
import {
  uploadFile as uploadFileToGCS,
  deleteFile as deleteFileFromGCS,
} from '@/lib/gcs';
import { v4 as uuidv4 } from 'uuid';

export interface ServiceResult<T> {
  success: boolean;
  data?: T;
  error?: string;
  details?: unknown;
  status?: number;
}

export interface UpdateCardData {
  title?: string;
  content?: Prisma.JsonValue;
  folderId?: string | null;
  tags?: string[];
}

const GCS_ALLOWED_MIME_TYPES = [
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
];
const GCS_MAX_SIZE_BYTES = 5 * 1024 * 1024;

async function _processAndLinkImages(
  blocks: StandardDocument,
  cardId: string,
  userId: string,
): Promise<string[]> {
  await prismaReady;
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

export async function getCardLogic(
  cardId: string,
  userId: string,
): Promise<
  ServiceResult<
    Prisma.KnowledgeCardGetPayload<{ include: { folder: true; tags: true } }>
  >
> {
  try {
    await prismaReady;
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

export async function updateCardLogic(
  cardId: string,
  userId: string,
  data: UpdateCardData,
): Promise<
  ServiceResult<
    Prisma.KnowledgeCardGetPayload<{ include: { folder: true; tags: true } }>
  >
> {
  try {
    await prismaReady;
    const existingCardForOwnershipCheck = await prisma.knowledgeCard.findUnique(
      {
        where: { id: cardId, userId: userId },
        select: { id: true },
      },
    );
    if (!existingCardForOwnershipCheck) {
      return {
        success: false,
        error: 'Card not found or not owned by user',
        status: 404,
      };
    }

    const imageRecordsInitiallyLinkedToCard = await prisma.imageRecord.findMany(
      {
        where: {
          knowledgeCardId: cardId,
          userId: userId,
        },
        select: { id: true, gcsPath: true },
      },
    );
    const initialImageRecordIds = imageRecordsInitiallyLinkedToCard
      ? imageRecordsInitiallyLinkedToCard.map((img) => img.id)
      : [];

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
      activeImageRecordIdsInNewContent = [...initialImageRecordIds];
      console.log(
        `[cardService] (updateCardLogic) Content not in update request. Assuming all ${initialImageRecordIds.length} initially linked images are still active for card ${cardId}.`,
      );
    }

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

    if (Object.keys(updatePayload).length > 0) {
      await prisma.knowledgeCard.update({
        where: { id: cardId, userId: userId },
        data: updatePayload,
      });
      console.log(
        `[cardService] (updateCardLogic) KnowledgeCard ${cardId} main fields updated.`,
      );
    } else if (!contentWasActuallyInRequest) {
      console.log(
        `[cardService] (updateCardLogic) No direct card fields to update for card ${cardId} and content not in request.`,
      );
    }

    if (activeImageRecordIdsInNewContent.length > 0) {
      await prisma.imageRecord.updateMany({
        where: {
          id: { in: activeImageRecordIdsInNewContent },
          userId: userId,
        },
        data: { knowledgeCardId: cardId },
      });
      console.log(
        `[cardService] (updateCardLogic) Linked/Re-linked ${activeImageRecordIdsInNewContent.length} active images to card ${cardId}. IDs: ${activeImageRecordIdsInNewContent.join(', ')}`,
      );
    }

    const potentiallyOrphanedIds = initialImageRecordIds.filter(
      (id) => !activeImageRecordIdsInNewContent.includes(id),
    );

    if (potentiallyOrphanedIds.length > 0) {
      console.log(
        `[cardService] (updateCardLogic) Card ${cardId} has ${potentiallyOrphanedIds.length} potentially orphaned ImageRecords. IDs: ${potentiallyOrphanedIds.join(', ')}`,
      );

      await prisma.imageRecord.updateMany({
        where: {
          id: { in: potentiallyOrphanedIds },
          userId: userId,
          knowledgeCardId: cardId,
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
        if (!imageRecordDetails) continue;

        const isStillLinkedToAnyCardByOwner =
          await prisma.imageRecord.findFirst({
            where: {
              id: orphanId,
              userId: userId,
              knowledgeCardId: { not: null },
            },
            select: { id: true, knowledgeCardId: true },
          });

        if (!isStillLinkedToAnyCardByOwner) {
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
            }
          }
          await prisma.imageRecord.delete({
            where: { id: orphanId, userId: userId },
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

    const fullyUpdatedCard = await prisma.knowledgeCard.findUnique({
      where: { id: cardId, userId: userId },
      include: { tags: true, folder: true },
    });

    if (!fullyUpdatedCard) {
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

export async function deleteCardLogic(
  cardId: string,
  userId: string,
): Promise<ServiceResult<Prisma.KnowledgeCardGetPayload<{}>>> {
  try {
    await prismaReady;
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

    const imageRecordsToDelete = await prisma.imageRecord.findMany({
      where: { knowledgeCardId: cardId },
      select: { gcsPath: true, id: true },
    });

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

    const deletedCard = await prisma.knowledgeCard.delete({
      where: { id: cardId },
    });

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