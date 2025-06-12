import { Prisma, KnowledgeCard } from '@prisma/client';
import prisma from '@/lib/prisma';
import {
  StandardDocument,
  isImageBlock,
  // MyAppImageBlockProps, // Removed unused import
} from '@/types/editorTypes';
import {
  uploadFile as uploadFileToGCS,
  getPublicUrl,
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

// This function is now responsible for converting data URLs to public GCS URLs
// and leaving existing URLs as they are. It no longer interacts with the database.
async function _convertDataUrlsToGcsUrls(
  blocks: StandardDocument,
  cardId: string,
  userId: string, // Keep userId for potential future ownership/logging
): Promise<void> { // This function now mutates the blocks directly and returns nothing.
  for (let i = 0; i < blocks.length; i++) {
    const currentBlock = blocks[i];

    if (isImageBlock(currentBlock)) {
      const imageProps = currentBlock.props;
      const originalUrl = imageProps.url;

      // Only process new images uploaded as data URIs
      if (
        typeof originalUrl === 'string' &&
        originalUrl.startsWith('data:image')
      ) {
        try {
          console.log(
            `[cardService] (_convertDataUrlsToGcsUrls) Processing data: URL for card context ${cardId}`,
          );
          const parts = originalUrl.split(',');
          if (parts.length < 2) {
            console.warn(
              '[cardService] (_convertDataUrlsToGcsUrls) Invalid data: URL format (missing comma). Skipping.',
            );
            continue;
          }
          const meta = parts[0];
          const base64Data = parts[1];
          const contentTypeMatch = meta.match(/data:(image\/[^;]+);base64/);
          if (!contentTypeMatch || !contentTypeMatch[1]) {
            console.warn(
              '[cardService] (_convertDataUrlsToGcsUrls) Could not determine content type from data: URL. Skipping.',
            );
            continue;
          }
          const contentType = contentTypeMatch[1];
          if (!GCS_ALLOWED_MIME_TYPES.includes(contentType.toLowerCase())) {
            console.warn(
              `[cardService] (_convertDataUrlsToGcsUrls) Unsupported content type from data: URL: ${contentType}. Skipping.`,
            );
            continue;
          }
          const buffer = Buffer.from(base64Data, 'base64');
          if (buffer.length > GCS_MAX_SIZE_BYTES) {
            console.warn(
              `[cardService] (_convertDataUrlsToGcsUrls) Image from data: URL exceeds size limit. Skipping.`,
            );
            continue;
          }

          const fileExtension = contentType.split('/')[1] || 'png';
          // Create a unique filename for GCS
          const gcsFilename = `user-${userId}/card-${cardId}/img-${uuidv4()}.${fileExtension}`;

          // Upload to GCS
          await uploadFileToGCS(
            buffer,
            gcsFilename,
            contentType,
          );

          // Get the public URL for the newly uploaded file
          const publicGcsUrl = getPublicUrl(gcsFilename);

          // Update the block's URL directly to the public GCS URL
          blocks[i] = {
            ...currentBlock,
            props: {
              ...imageProps,
              url: publicGcsUrl, // The final public URL
            },
          };

          console.log(
            `[cardService] (_convertDataUrlsToGcsUrls) Successfully processed data: URL. New public URL: ${publicGcsUrl}`,
          );
        } catch (error) {
          console.error(
            `[cardService] (_convertDataUrlsToGcsUrls) Failed to process data: URL for card context ${cardId}:`,
            error instanceof Error ? error.message : error,
          );
          // If processing fails, we leave the original data: URL in place for now.
          // The frontend might attempt to resave.
        }
      }
      // We no longer need to check for /api/images/serve URLs, as they are obsolete.
      // Existing http/https urls are left as is.
    }

    // Recurse for nested blocks (children)
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
        await _convertDataUrlsToGcsUrls(
          blockToProcessForChildren.children as StandardDocument,
          cardId,
          userId,
        );
      }
    }
  }
  // No return value, as we are mutating the content object directly.
}

// This function is now much simpler. It no longer tracks image record IDs.
// It just processes the content and returns it.
export async function processCardContentImages(
  content: Prisma.JsonValue | undefined | null,
  cardId: string,
  userId: string,
): Promise<Prisma.JsonValue | undefined | null> {
  if (!content || !Array.isArray(content) || content.length === 0) {
    return content;
  }

  let mutableContent: StandardDocument;
  try {
    // Deep clone the content to avoid mutating the original object passed in.
    mutableContent = JSON.parse(JSON.stringify(content)) as StandardDocument;
  } catch (cloneError) {
    console.error(
      '[cardService] (processCardContentImages) Failed to clone content for image processing. Returning original content.',
      cloneError,
    );
    return content;
  }

  await _convertDataUrlsToGcsUrls(
    mutableContent,
    cardId,
    userId,
  );

  // Return the content with data: URIs replaced by GCS URLs.
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
    const card = await prisma.knowledgeCard.findUnique({
      where: { id: cardId, userId },
      select: { tags: true }, // Select current tags for comparison
    });

    if (!card) {
      return { success: false, error: 'Card not found', status: 404 };
    }

    // Image processing logic is now simplified
    const processedContent = data.content
      ? await processCardContentImages(data.content, cardId, userId)
      : undefined;

    // The rest of the logic can now be simplified as it doesn't need to handle image records.

    const updatePayload: Prisma.KnowledgeCardUpdateInput = {};

    if (data.title !== undefined) {
      updatePayload.title = data.title;
    }
    if (processedContent !== undefined) {
      // Correctly handle setting JSON field to null
      if (processedContent === null) {
        updatePayload.content = Prisma.JsonNull;
      } else {
        updatePayload.content = processedContent;
      }
    }
    if (data.folderId !== undefined) {
      updatePayload.folder =
        data.folderId === null
          ? { disconnect: true }
          : { connect: { id: data.folderId } };
    }

    // --- Tag Management ---
    const currentTagNames = new Set(card.tags.map((t) => t.name));
    const newTagNames = new Set(data.tags || []);

    const tagsToConnect = [...newTagNames].filter(
      (tagName) => !currentTagNames.has(tagName),
    );
    const tagsToDisconnect = [...currentTagNames].filter(
      (tagName) => !newTagNames.has(tagName),
    );

    if (tagsToConnect.length > 0 || tagsToDisconnect.length > 0) {
      updatePayload.tags = {
        connectOrCreate: tagsToConnect.map((name) => ({
          where: { name },
          create: { name },
        })),
        disconnect: tagsToDisconnect.map((name) => ({ name })),
      };
    }
    // --- End Tag Management ---

    const updatedCard = await prisma.knowledgeCard.update({
      where: { id: cardId, userId },
      data: updatePayload,
      include: { folder: true, tags: true },
    });

    return { success: true, data: updatedCard };
  } catch (error) {
    console.error(`[cardService] (updateCardLogic) Error:`, error);
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      if (error.code === 'P2025') {
        return {
          success: false,
          error: 'A resource (like a folder or tag) was not found.',
          status: 404,
          details: error.meta,
        };
      }
    }
    return {
      success: false,
      error: 'Failed to update card.',
      status: 500,
      details: error,
    };
  }
}

// --- DELETE Card Logic ---
export async function deleteCardLogic(
  cardId: string,
  userId: string,
): Promise<ServiceResult<KnowledgeCard>> {
  try {
    // Note: We are not deleting images from GCS upon card deletion.
    // This is a business decision. Implementing a cleanup mechanism
    // would require parsing the content for GCS URLs before deletion.
    // For now, images will be orphaned.

    const deletedCard = await prisma.knowledgeCard.delete({
      where: { id: cardId, userId: userId },
    });
    return { success: true, data: deletedCard };
  } catch (error) {
    console.error(`[cardService] (deleteCardLogic) Error:`, error);
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      if (error.code === 'P2025') {
        return {
          success: false,
          error: 'Card not found',
          status: 404,
          details: error.meta,
        };
      }
    }
    return {
      success: false,
      error: 'Failed to delete card.',
      status: 500,
      details: error,
    };
  }
}
