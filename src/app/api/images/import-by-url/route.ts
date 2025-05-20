import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import prisma from '@/lib/prisma';
import { z } from 'zod';
import { uploadFile } from '@/lib/gcs'; // Assuming this can take a Buffer

// Define a schema for the request body using Zod
const importRequestSchema = z.object({
  externalImageUrl: z.string().url({ message: 'Invalid URL format' }),
});

// Define constants for validation - can be shared or kept here
// These should ideally match or be configurable with imageUploadService
const ALLOWED_MIME_TYPES_FROM_URL = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
];
const MAX_FILE_SIZE_MB_FROM_URL = 5; // 5MB
const MAX_FILE_SIZE_BYTES_FROM_URL = MAX_FILE_SIZE_MB_FROM_URL * 1024 * 1024;

export async function POST(request: NextRequest) {
  console.log('[/api/images/import-by-url] POST request received');
  const session = await getServerSession(authOptions);

  if (!session || !session.user || !session.user.id) {
    console.log(
      '[/api/images/import-by-url] Unauthorized: No session or user ID',
    );
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  const userId = session.user.id;

  let requestBody;
  try {
    requestBody = await request.json();
  } catch (error) {
    console.log(
      '[/api/images/import-by-url] Invalid JSON in request body:',
      error,
    );
    return NextResponse.json({ error: 'Invalid JSON format' }, { status: 400 });
  }

  const parsedRequest = importRequestSchema.safeParse(requestBody);
  if (!parsedRequest.success) {
    console.log(
      '[/api/images/import-by-url] Invalid request body:',
      parsedRequest.error.flatten(),
    );
    return NextResponse.json(
      { error: 'Invalid request body', details: parsedRequest.error.flatten() },
      { status: 400 },
    );
  }

  const { externalImageUrl } = parsedRequest.data;
  console.log(
    `[/api/images/import-by-url] Processing URL: ${externalImageUrl} for user ${userId}`,
  );

  try {
    // 1. Download the image
    let imageResponse;
    try {
      imageResponse = await fetch(externalImageUrl);
      if (!imageResponse.ok) {
        throw new Error(
          `Failed to fetch image. Status: ${imageResponse.status}`,
        );
      }
    } catch (fetchError: unknown) {
      console.error(
        `[/api/images/import-by-url] Error fetching image from URL ${externalImageUrl}:`,
        fetchError,
      );
      const message =
        fetchError instanceof Error ? fetchError.message : String(fetchError);
      return NextResponse.json(
        { error: 'Failed to download image from URL', details: message },
        { status: 400 },
      );
    }

    const contentType = imageResponse.headers.get('content-type');
    const contentLength = imageResponse.headers.get('content-length');

    // 2. Validate Content-Type
    if (
      !contentType ||
      !ALLOWED_MIME_TYPES_FROM_URL.includes(contentType.toLowerCase())
    ) {
      console.log(
        `[/api/images/import-by-url] Invalid content type: ${contentType}`,
      );
      return NextResponse.json(
        {
          error: `Invalid image type. Allowed types: ${ALLOWED_MIME_TYPES_FROM_URL.join(', ')}`,
        },
        { status: 400 },
      );
    }

    // 3. Validate Content-Length (if available)
    if (
      contentLength &&
      parseInt(contentLength, 10) > MAX_FILE_SIZE_BYTES_FROM_URL
    ) {
      console.log(
        `[/api/images/import-by-url] File too large: ${contentLength} bytes`,
      );
      return NextResponse.json(
        {
          error: `Image is too large. Maximum size: ${MAX_FILE_SIZE_MB_FROM_URL}MB`,
        },
        { status: 400 },
      );
    }

    const imageBuffer = Buffer.from(await imageResponse.arrayBuffer());

    // 4. Double check buffer size if contentLength was not available or unreliable
    if (imageBuffer.length > MAX_FILE_SIZE_BYTES_FROM_URL) {
      console.log(
        `[/api/images/import-by-url] File too large (buffer check): ${imageBuffer.length} bytes`,
      );
      return NextResponse.json(
        {
          error: `Image is too large. Maximum size: ${MAX_FILE_SIZE_MB_FROM_URL}MB`,
        },
        { status: 400 },
      );
    }

    // 5. Determine original filename (can be tricky)
    let originalFilename = 'image_from_url.png'; // Default
    try {
      const urlPath = new URL(externalImageUrl).pathname;
      const filenameFromPath = urlPath.substring(urlPath.lastIndexOf('/') + 1);
      if (filenameFromPath) {
        originalFilename = decodeURIComponent(filenameFromPath);
      }
    } catch {
      // Invalid URL or no path, use default
      console.warn(
        `[/api/images/import-by-url] Could not determine filename from URL: ${externalImageUrl}, using default.`,
      );
    }
    // Ensure filename has a common image extension if possible, based on contentType
    if (!originalFilename.match(/\.(jpeg|jpg|png|gif|webp)$/i)) {
      const ext = contentType.split('/')[1] || 'png';
      originalFilename = `image_from_url.${ext}`;
    }

    // 6. Upload to GCS (reusing your existing uploadFile function)
    console.log(
      `[/api/images/import-by-url] Uploading to GCS: ${originalFilename}, type: ${contentType}, size: ${imageBuffer.length}`,
    );
    const gcsFile = await uploadFile(
      imageBuffer,
      originalFilename,
      contentType,
      // We might need to adjust uploadFile if it expects UploadOptions and we have different ones here
    );
    console.log('[/api/images/import-by-url] GCS upload result:', gcsFile);

    // 7. Create ImageRecord in Prisma
    // Let Prisma generate the CUID for id
    // const imageRecordId = randomUUID(); // REMOVED: Let Prisma generate CUID
    // const appServedUrl = `/api/images/serve/${imageRecordId}`; // REMOVED: Construct after creation

    const newImageRecord = await prisma.imageRecord.create({
      data: {
        // id: imageRecordId, // REMOVED: Let Prisma generate CUID
        userId: userId,
        gcsPath: gcsFile.filename, // uploadFile returns the GCS filename
        contentType: gcsFile.contentType,
        originalFilename: originalFilename, // The name we determined
        size: gcsFile.size,
        appServedUrl: '', // Placeholder, will be updated next
        // knowledgeCardId will be null initially
      },
    });
    console.log(
      '[/api/images/import-by-url] ImageRecord created (initial):',
      newImageRecord.id,
    );

    // Construct the appServedUrl using the generated ID and update the record
    const appServedUrl = `/api/images/serve/${newImageRecord.id}`;
    const updatedImageRecord = await prisma.imageRecord.update({
      where: { id: newImageRecord.id },
      data: { appServedUrl: appServedUrl },
    });
    console.log(
      '[/api/images/import-by-url] ImageRecord updated with appServedUrl:',
      updatedImageRecord.id,
    );

    // 8. Return success response
    return NextResponse.json({
      success: true,
      appServedUrl: updatedImageRecord.appServedUrl, // Use appServedUrl from the updated record
      imageRecordId: updatedImageRecord.id, // Use id from the updated record
    });
  } catch (error: unknown) {
    console.error('[/api/images/import-by-url] Internal server error:', error);
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: 'Failed to import image by URL', details: message },
      { status: 500 },
    );
  }
}
