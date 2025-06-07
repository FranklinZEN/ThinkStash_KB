import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth';
import prisma from '@/lib/prisma';
import { getBucket } from '@/lib/gcs';

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ imageRecordId: string }> },
) {
  let imageRecordId: string | undefined = undefined;
  try {
    const routeParams = await context.params;
    imageRecordId = routeParams.imageRecordId;

    console.log(`API /images/serve/${imageRecordId} (GET) called`);

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

    const imageRecord = await prisma.imageRecord.findUnique({
      where: { id: imageRecordId },
    });

    if (!imageRecord) {
      console.log(
        `[/api/images/serve] Not Found: No ImageRecord for ID ${imageRecordId}`,
      );
      return NextResponse.json({ error: 'Image not found' }, { status: 404 });
    }

    console.log(
      `[/api/images/serve] Streaming image from GCS path: ${imageRecord.gcsPath}`,
    );

    const bucket = getBucket();
    const file = bucket.file(imageRecord.gcsPath);

    const [exists] = await file.exists();
    if (!exists) {
      console.error(
        `[/api/images/serve] GCS Error: File not found at path ${imageRecord.gcsPath}`,
      );
      return NextResponse.json(
        { error: 'Image file not found in storage' },
        { status: 404 },
      );
    }

    const stream = file.createReadStream();

    const responseHeaders = new Headers();
    responseHeaders.set('Content-Type', imageRecord.contentType);
    responseHeaders.set('Cache-Control', 'public, max-age=604800, immutable');

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
    console.error(`Error in /images/serve/${imageRecordId || 'unknown_id'} (GET):`, error);
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    return NextResponse.json(
      { error: 'Internal Server Error', details: errorMessage },
      { status: 500 },
    );
  }
}
