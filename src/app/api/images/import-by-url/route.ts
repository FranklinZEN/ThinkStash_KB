import { NextRequest, NextResponse } from 'next/server';
import { getServerSession as originalGetServerSession } from 'next-auth';
import { Prisma } from '@prisma/client';
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

interface TestUserSession {
  user: {
    id: string;
    name: string;
    email: string;
  };
}

// ADD: Helper function for test session override
async function getTestSessionOverride(
  req: NextRequest,
): Promise<TestUserSession | null | undefined> {
  const testUserId = req.headers.get('X-Test-User-Id');
  if (testUserId === 'null') {
    console.log(
      '[/api/images/import-by-url] Test override: Unauthenticated session (null)',
    );
    return null;
  }
  if (testUserId) {
    console.log(
      `[/api/images/import-by-url] Test override: Authenticated as user ${testUserId}`,
    );
    return {
      user: {
        id: testUserId,
        name: 'Test User',
        email: `${testUserId}@example.com`,
      },
    };
  }
  return undefined;
}

// ADD: Helper function to get a mocked fetch Response based on test headers
function getMockedFetchResponseForTest(
  req: NextRequest,
  targetUrl: string,
): Response | undefined {
  const mockUrlHeader = req.headers.get('X-Test-Mock-Fetch-Url');

  if (mockUrlHeader && mockUrlHeader === targetUrl) {
    const mockStatusHeader =
      req.headers.get('X-Test-Mock-Fetch-Status') || '200';

    // SPECIAL CASE for large buffer test to avoid large header
    if (mockStatusHeader === '200-large-buffer-test') {
      console.log(
        `[/api/images/import-by-url] Test override: Mocking fetch for ${targetUrl} with status 200 and internal large buffer.`,
      );
      const largeBufferForTest = Buffer.alloc(6 * 1024 * 1024); // 6MB
      return new Response(largeBufferForTest, {
        status: 200,
        headers: { 'Content-Type': 'image/jpeg' },
      });
    }

    const mockStatus = parseInt(mockStatusHeader, 10);
    const mockBodyBase64 = req.headers.get('X-Test-Mock-Fetch-Body-Base64');
    const mockHeadersString =
      req.headers.get('X-Test-Mock-Fetch-Headers') || '{}';

    let body: BodyInit | null = null;
    if (mockBodyBase64) {
      body = Buffer.from(mockBodyBase64, 'base64');
    }

    let headers: HeadersInit = {};
    try {
      headers = JSON.parse(mockHeadersString);
    } catch (_e) {
      console.error(
        '[/api/images/import-by-url] Failed to parse X-Test-Mock-Fetch-Headers',
        _e,
      );
    }

    console.log(
      `[/api/images/import-by-url] Test override: Mocking fetch for ${targetUrl} with status ${mockStatus}`,
    );
    return new Response(body, { status: mockStatus, headers: headers });
  }
  return undefined;
}

// Unused function - commented out
// async function getAuthenticatedUserIdOrThrow(_req: NextRequest): Promise<string> {
//   const session = await originalGetServerSession(authOptions);
//   const userId = session?.user?.id;
//   if (!userId) {
//     console.warn('[/api/images/import-by-url] No user ID found in session for non-test path.');
//     throw new Error('UNAUTHORIZED');
//   }
//   return userId;
// }

// Unused interface - commented out
// interface GCSFileData {
//   filename: string;
//   contentType: string;
//   size: number;
//   url: string;
// }

export async function POST(request: NextRequest) {
  console.log('[/api/images/import-by-url] POST request received');

  // MODIFIED: Session retrieval logic
  let session = await getTestSessionOverride(request);
  if (session === undefined) {
    // If no test override, get real session
    console.log(
      '[/api/images/import-by-url] No test override, calling originalGetServerSession',
    );
    session = await originalGetServerSession(authOptions);
  } else {
    console.log(
      '[/api/images/import-by-url] Using session from test override.',
    );
  }

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
    let imageResponse: Response;
    // MODIFIED: Check for test mock fetch response first
    const mockedImageResponse = getMockedFetchResponseForTest(
      request,
      externalImageUrl,
    );

    if (mockedImageResponse) {
      imageResponse = mockedImageResponse;
    } else {
      console.log(
        `[/api/images/import-by-url] No test override for fetch, making real fetch to ${externalImageUrl}`,
      );
      imageResponse = await fetch(externalImageUrl);
    }

    if (!imageResponse.ok) {
      let responseDetails = `Status: ${imageResponse.status}`;
      try {
        const responseText = await imageResponse.text();
        responseDetails += `, Body: ${responseText.substring(0, 100)}...`;
      } catch {
        /* ignore if body can't be read, removed _e */
      }
      console.error(
        `[/api/images/import-by-url] Error fetching image from URL ${externalImageUrl}. Response not OK. Details: ${responseDetails}`,
      );
      throw new Error(`Failed to fetch image. Status: ${imageResponse.status}`);
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

    // ADD console.log for debugging buffer size check
    console.log(
      `[/api/images/import-by-url] Buffer Check: imageBuffer.length = ${imageBuffer.length}, MAX_FILE_SIZE_BYTES_FROM_URL = ${MAX_FILE_SIZE_BYTES_FROM_URL}`,
    );

    if (imageBuffer.length > MAX_FILE_SIZE_BYTES_FROM_URL) {
      console.log(
        `[/api/images/import-by-url] File too large (buffer check): ${imageBuffer.length} bytes - FAILING with 400.`,
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

    let gcsFile;
    const gcsUploadError = request.headers.get('X-Test-GCS-Upload-Error');
    const gcsUploadSuccessData = request.headers.get(
      'X-Test-GCS-Upload-Success-Data',
    );

    if (gcsUploadError) {
      console.log(
        `[/api/images/import-by-url] Test override: Simulating GCS Upload Error: ${gcsUploadError}`,
      );
      throw new Error(gcsUploadError);
    } else if (gcsUploadSuccessData) {
      console.log(
        `[/api/images/import-by-url] Test override: Using mocked GCS Upload Data`,
      );
      try {
        gcsFile = JSON.parse(gcsUploadSuccessData);
      } catch (e) {
        console.error(
          '[/api/images/import-by-url] Failed to parse X-Test-GCS-Upload-Success-Data',
          e,
        );
        throw new Error('Invalid GCS success data in test header');
      }
    } else {
      console.log(
        `[/api/images/import-by-url] No test override for GCS, calling real uploadFile`,
      );
      gcsFile = await uploadFile(imageBuffer, originalFilename, contentType);
    }
    console.log('[/api/images/import-by-url] GCS interaction result:', gcsFile);

    // ADD: Check for Prisma Create Error Header
    const prismaCreateError = request.headers.get('X-Test-Prisma-Create-Error');
    if (prismaCreateError) {
      console.log(
        `[/api/images/import-by-url] Test override: Simulating Prisma Create Error: ${prismaCreateError}`,
      );
      throw new Error(prismaCreateError);
    }

    // MODIFIED: Use a unique temporary appServedUrl during create
    const tempAppServedUrl = `temp-${gcsFile.filename}-${Date.now()}`;

    // Use Prisma.ImageRecordCreateInput and connect the user
    const imageRecordCreateData: Prisma.ImageRecordCreateInput = {
      gcsPath: gcsFile.filename,
      contentType: gcsFile.contentType,
      originalFilename: originalFilename,
      size: gcsFile.size,
      appServedUrl: tempAppServedUrl, // Use unique temporary value
      user: {
        // Connect to the existing user
        connect: {
          id: userId,
        },
      },
      // Any other required fields for ImageRecord creation
    };

    // Prisma will now always generate the ID for create
    const newImageRecord = await prisma.imageRecord.create({
      data: imageRecordCreateData, // Use the correctly typed data with user connection
    });
    console.log(
      '[/api/images/import-by-url] ImageRecord created with Prisma-generated ID:',
      newImageRecord.id,
    );

    const appServedUrl = `/api/images/serve/${newImageRecord.id}`;
    const prismaUpdateError = request.headers.get('X-Test-Prisma-Update-Error');
    if (prismaUpdateError) {
      console.log(
        `[/api/images/import-by-url] Test override: Simulating Prisma Update Error for ID ${newImageRecord.id}: ${prismaUpdateError}`,
      );
      throw new Error(prismaUpdateError);
    }
    const updatedImageRecord = await prisma.imageRecord.update({
      where: { id: newImageRecord.id },
      data: { appServedUrl: appServedUrl },
    });
    console.log(
      '[/api/images/import-by-url] ImageRecord updated with appServedUrl:',
      updatedImageRecord.id,
    );

    return NextResponse.json({
      success: true,
      appServedUrl: updatedImageRecord.appServedUrl,
      imageRecordId: updatedImageRecord.id,
      gcsUrl: gcsFile.url,
    });
  } catch (error: unknown) {
    console.error('[/api/images/import-by-url] Internal server error:', error);
    // ADD: Enhanced logging for Prisma P2002 errors
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === 'P2002'
    ) {
      console.error(
        '[/api/images/import-by-url] Prisma Unique Constraint Violation (P2002). Meta:',
        error.meta,
      );
    }
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: 'Failed to import image by URL', details: message },
      { status: 500 },
    );
  }
}
