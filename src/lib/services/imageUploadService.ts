import { PrismaClient } from '@prisma/client'; // Remove Prisma
import { uploadFile, UploadedFile as GCSUploadedFile } from '@/lib/gcs';

// Define constants for validation - can be shared or kept here
const ALLOWED_MIME_TYPES = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
];
const MAX_FILE_SIZE_MB = 5; // 5MB
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

export interface ImageUploadInput {
  userId: string;
  fileBuffer: Buffer;
  originalFilename: string;
  contentType: string;
  fileSize: number;
}

export interface ImageUploadResult {
  success: boolean;
  appServedUrl?: string;
  imageRecordId?: string;
  error?: string;
  details?: string;
  status?: number; // HTTP status code for the route to use
}

// Updated to use indexed access types from PrismaClient
export interface ImageRecordPrismaSubset {
  imageRecord: {
    create: PrismaClient['imageRecord']['create'];
    update: PrismaClient['imageRecord']['update'];
  };
}

export async function handleImageUploadLogic(
  input: ImageUploadInput,
  prismaInstance: PrismaClient, // Changed to PrismaClient
): Promise<ImageUploadResult> {
  console.log(
    '[imageUploadService] Processing image upload for user:',
    input.userId,
  );
  try {
    // Validate MIME type
    if (!ALLOWED_MIME_TYPES.includes(input.contentType)) {
      console.error(
        `[imageUploadService] Invalid file type: ${input.contentType}`,
      );
      return {
        success: false,
        error: `Invalid file type. Allowed types are: ${ALLOWED_MIME_TYPES.join(', ')}.`,
        status: 400,
      };
    }

    // Validate file size
    if (input.fileSize > MAX_FILE_SIZE_BYTES) {
      console.error(
        `[imageUploadService] File too large: ${input.fileSize} bytes.`,
      );
      return {
        success: false,
        error: `File exceeds maximum size of ${MAX_FILE_SIZE_MB}MB.`,
        status: 400,
      };
    }

    // Upload to GCS
    console.log(
      `[imageUploadService] Calling uploadFile for ${input.originalFilename}...`,
    );
    const gcsUploadResult: GCSUploadedFile = await uploadFile(
      input.fileBuffer,
      input.originalFilename,
      input.contentType,
    );
    console.log('[imageUploadService] uploadFile result:', gcsUploadResult);

    // Create ImageRecord in the database
    console.log('[imageUploadService] Creating ImageRecord...');
    const newImageRecord = await prismaInstance.imageRecord.create({
      data: {
        userId: input.userId,
        gcsPath: gcsUploadResult.filename, // filename from GCS upload result
        contentType: input.contentType,
        originalFilename: input.originalFilename,
        size: input.fileSize,
        appServedUrl: '', // Placeholder, will be updated shortly
      },
      select: {
        id: true,
        userId: true,
        gcsPath: true,
        contentType: true,
        originalFilename: true,
        size: true,
        appServedUrl: true,
        knowledgeCardId: true,
        createdAt: true,
        updatedAt: true,
      },
    });

    const appServedUrl = `/api/images/serve/${newImageRecord.id}`;

    // Update ImageRecord with the correct appServedUrl
    const updatedImageRecord = await prismaInstance.imageRecord.update({
      where: { id: newImageRecord.id },
      data: { appServedUrl: appServedUrl },
      select: { id: true, appServedUrl: true },
    });
    console.log(
      '[imageUploadService] ImageRecord created/updated:',
      updatedImageRecord.id,
    );

    return {
      success: true,
      appServedUrl: updatedImageRecord.appServedUrl,
      imageRecordId: updatedImageRecord.id,
      status: 200, // Or 201 if you prefer for creation
    };
  } catch (error: unknown) {
    console.error(
      '[imageUploadService] Error during image upload logic:',
      error,
    );
    let errorMessage = 'An unknown error occurred during image processing.';
    let errorDetails: string | undefined = undefined;

    if (error instanceof Error) {
      errorMessage = error.message;
      if (error.name === 'PrismaClientKnownRequestError') {
        console.error('[imageUploadService] Prisma Error:', error.message);
        errorMessage = 'Database operation failed during image processing.';
        errorDetails = error.message;
      } else if (errorMessage.includes('GCS')) {
        // Example for GCS specific error check from uploadFile
        errorMessage = 'GCS operation failed during image processing.';
        errorDetails = error.message;
      }
    } else if (typeof error === 'string') {
      errorMessage = error;
    }

    return {
      success: false,
      error: errorMessage,
      details: errorDetails,
      status: 500,
    };
  }
}
