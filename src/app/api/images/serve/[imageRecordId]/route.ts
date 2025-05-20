import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import prisma from '@/lib/prisma';
import { getBucket } from '@/lib/gcs'; // Changed from 'storage' to 'getBucket'

// Define an interface for the route parameters
// interface RouteHandlerContext { // Keeping this commented out for clarity with the 'any' type below
//   params: {
//     imageRecordId: string;
//   };
// }

export async function GET(
  request: NextRequest,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  context: any, // Kept as any with eslint-disable due to known Next.js typing issues
) {
  // We still expect context.params.imageRecordId to exist and be a string based on runtime behavior.
  const imageRecordId = context.params?.imageRecordId as string;

  console.log(
    `[/api/images/serve] GET request for imageRecordId: ${imageRecordId}`,
  );
  const session = await getServerSession(authOptions);

  if (!session || !session.user || !session.user.id) {
    console.log('[/api/images/serve] Unauthorized: No session or user ID');
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  if (!imageRecordId) {
    console.log('[/api/images/serve] Bad Request: Missing imageRecordId');
    return NextResponse.json(
      { error: 'Bad Request: Missing imageRecordId' },
      { status: 400 },
    );
  }

  const gcsBucketName = process.env.GCS_BUCKET_NAME;
  if (!gcsBucketName) {
    console.error(
      '[/api/images/serve] GCS_BUCKET_NAME environment variable is not set',
    );
    return NextResponse.json(
      { error: 'Server configuration error for GCS bucket.' },
      { status: 500 },
    );
  }

  try {
    const imageRecord = await prisma.imageRecord.findUnique({
      where: { id: imageRecordId },
    });

    if (!imageRecord) {
      console.log(
        `[/api/images/serve] Not Found: No ImageRecord for ID ${imageRecordId}`,
      );
      return NextResponse.json({ error: 'Image not found' }, { status: 404 });
    }

    // Basic authorization: For now, any authenticated user can access any image
    // This will be enhanced in TS-MEDIA-AUTH-1 for granular authorization
    // if (imageRecord.userId !== session.user.id) {
    //   // Add logic here if images are private to users even before granular auth
    //   // For now, allowing access if authenticated and record exists
    //   console.log(`[/api/images/serve] Forbidden: User ${session.user.id} trying to access image of user ${imageRecord.userId}`);
    //   return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    // }

    console.log(
      `[/api/images/serve] Streaming image from GCS path: ${imageRecord.gcsPath}`,
    );

    // const storage = getStorage(); // No longer needed, storage is imported directly
    const bucket = getBucket(); // NEW WAY
    const file = bucket.file(imageRecord.gcsPath);

    // Check if file exists in GCS
    const [exists] = await file.exists();
    if (!exists) {
      console.error(
        `[/api/images/serve] GCS Error: File not found at path ${imageRecord.gcsPath}`,
      );
      // Potentially mark imageRecord as problematic or log for cleanup
      return NextResponse.json(
        { error: 'Image file not found in storage' },
        { status: 404 },
      );
    }

    // Get a readable stream for the file
    const stream = file.createReadStream();

    // For NextResponse with a stream, we need to set headers for content type
    // and potentially content length if known, and cache control.
    const responseHeaders = new Headers();
    responseHeaders.set('Content-Type', imageRecord.contentType);
    responseHeaders.set('Cache-Control', 'public, max-age=604800, immutable'); // Cache for 7 days

    // Use a ReadableStream to pipe the GCS stream to the NextResponse
    // Convert Node.js stream to Web API ReadableStream
    const webStream = new ReadableStream({
      start(controller) {
        stream.on('data', (chunk) => controller.enqueue(chunk));
        stream.on('end', () => controller.close());
        stream.on('error', (err) => controller.error(err));
      },
      cancel() {
        stream.destroy();
      },
    });

    return new NextResponse(webStream, {
      status: 200,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error(
      `[/api/images/serve] Internal Server Error while serving image ${imageRecordId}:`,
      error,
    );
    const errorMessage =
      error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { error: 'Internal Server Error', details: errorMessage },
      { status: 500 },
    );
  }
}
