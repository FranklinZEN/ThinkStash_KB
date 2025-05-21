import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import {
  handleImageUploadLogic,
  ImageUploadInput,
} from '@/lib/services/imageUploadService';
import prisma from '@/lib/prisma'; // Import the actual prisma instance
// import { z } from 'zod'; // Removed unused import
import { UploadedFileMetadataSchema } from '@/lib/validators/editorValidators'; // Import the new schema

// Define constants for validation - these are now primarily handled in the service, but good for reference or quick checks if needed.
// const ALLOWED_MIME_TYPES = [ // Remove unused
//   'image/jpeg',
//   'image/png',
//   'image/gif',
//   'image/webp',
// ];
// const MAX_FILE_SIZE_MB = 5; // Remove unused (MAX_FILE_SIZE_BYTES was derived but also unused)
// const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024; // Remove unused

export async function POST(request: NextRequest) {
  console.log('[/api/upload/image] POST request received');
  try {
    // Check authentication
    console.log('Checking session...');
    const session = await getServerSession(authOptions);
    if (!session || !session.user?.id) {
      console.error(
        '[/api/upload/image] Unauthorized: No session or user ID found',
      );
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userId = session.user.id;
    console.log('[/api/upload/image] Session valid for user ID:', userId);

    // Get the form data
    console.log('[/api/upload/image] Parsing form data...');
    const formData = await request.formData();
    const file = formData.get('file') as File | null; // Ensure it can be null

    if (!file) {
      console.error('[/api/upload/image] No file provided in form data');
      return NextResponse.json({ error: 'No file provided' }, { status: 400 });
    }
    console.log(
      `[/api/upload/image] File received: ${file.name}, type: ${file.type}, size: ${file.size}`,
    );

    // Validate file metadata using Zod
    const fileMetadata = {
      name: file.name,
      type: file.type,
      size: file.size,
    };
    const metadataValidation =
      UploadedFileMetadataSchema.safeParse(fileMetadata);

    if (!metadataValidation.success) {
      console.error(
        '[/api/upload/image] File metadata validation failed:',
        metadataValidation.error.flatten().fieldErrors,
      );
      return NextResponse.json(
        {
          error: 'Invalid file metadata',
          details: metadataValidation.error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }
    // metadataValidation.data now contains the validated and typed metadata, though we already have it in `file`.

    // Convert File to Buffer
    console.log('[/api/upload/image] Converting file to buffer...');
    const buffer = Buffer.from(await file.arrayBuffer());
    console.log(
      '[/api/upload/image] File converted to buffer, length:',
      buffer.length,
    );

    // Prepare input for the service function
    const serviceInput: ImageUploadInput = {
      userId,
      fileBuffer: buffer,
      originalFilename: file.name,
      contentType: file.type,
      fileSize: file.size,
    };

    // Call the service function
    console.log('[/api/upload/image] Calling imageUploadService...');
    const result = await handleImageUploadLogic(serviceInput, prisma);
    console.log('[/api/upload/image] imageUploadService result:', result);

    if (result.success) {
      return NextResponse.json(
        {
          success: true,
          appServedUrl: result.appServedUrl,
          imageRecordId: result.imageRecordId,
        },
        { status: result.status || 200 },
      ); // Use status from service or default to 200
    } else {
      return NextResponse.json(
        { error: result.error, details: result.details },
        { status: result.status || 500 }, // Use status from service or default to 500
      );
    }
  } catch (error: unknown) {
    console.error('[/api/upload/image] Unexpected error in API route:', error);
    let errorMessage = 'An unexpected error occurred in the API route.';
    if (error instanceof Error) {
      errorMessage = error.message;
    }
    return NextResponse.json(
      { error: 'Failed to process upload request.', details: errorMessage },
      { status: 500 },
    );
  }
}

// bodyParser config might not be needed if Next.js App Router handles FormData parsing adequately by default.
// If you switch to formidable or another parser in the future, you might need it.
// export const config = {
//   api: {
//     bodyParser: false,
//   },
// };
