import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path to your authOptions
import prisma from '@/lib/prisma'; // Adjust path to your Prisma client
import { Storage } from '@google-cloud/storage';
import { Readable } from 'stream';

const GCS_MEDIA_BUCKET_NAME = process.env.GCS_MEDIA_BUCKET_NAME;

if (!GCS_MEDIA_BUCKET_NAME) {
  console.error('GCS_MEDIA_BUCKET_NAME environment variable is not set for image serving.');
}

const storage = new Storage();
const bucket = GCS_MEDIA_BUCKET_NAME ? storage.bucket(GCS_MEDIA_BUCKET_NAME) : null;

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ gcsPath: string[] }> }
) {
  const resolvedParams = await context.params;

  if (!bucket) {
    console.error('[GET /api/images] GCS bucket not configured.');
    return NextResponse.json({ error: 'Image serving misconfigured.' }, { status: 500 });
  }

  const session = await getServerSession(authOptions);
  if (!session || !session.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  const requestingUserId = session.user.id;

  // Reconstruct the GCS path from the URL segments
  // e.g., if URL is /api/images/images/userId/filename.jpg, params.gcsPath will be ["images", "userId", "filename.jpg"]
  const fullGcsPath = resolvedParams.gcsPath.join('/');

  if (!fullGcsPath) {
    return NextResponse.json({ error: 'Image path not provided.' }, { status: 400 });
  }

  try {
    // 1. Find ImageMetadata using the gcsPath
    const imageMetadata = await prisma.imageMetadata.findUnique({
      where: { gcsPath: fullGcsPath },
      include: {
        knowledgeCard: {
          select: { userId: true }, // Select the owner ID of the card
        },
      },
    });

    if (!imageMetadata) {
      console.warn(`[GET /api/images] ImageMetadata not found for gcsPath: ${fullGcsPath}`);
      return NextResponse.json({ error: 'Image not found.' }, { status: 404 });
    }

    // 2. Authorization Check:
    // In a personal knowledge base, the image uploader (imageMetadata.userId) 
    // and the card owner (imageMetadata.knowledgeCard?.userId) should typically be the same.
    // We primarily care if the *requesting user* owns the *card* the image is associated with.
    
    const cardOwnerId = imageMetadata.knowledgeCard?.userId;

    if (!cardOwnerId) {
        console.error(`[GET /api/images] ImageMetadata ${imageMetadata.id} (gcsPath: ${fullGcsPath}) is not linked to a KnowledgeCard or card has no owner.`);
        // This scenario implies an orphaned image or data integrity issue.
        return NextResponse.json({ error: 'Image cannot be accessed. Data inconsistency.' }, { status: 500 });
    }

    if (requestingUserId !== cardOwnerId) {
      console.warn(
        `[GET /api/images] Forbidden access attempt: User ${requestingUserId} tried to access image ${fullGcsPath} owned by card user ${cardOwnerId}`
      );
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    // 3. Serve the file from GCS
    const file = bucket.file(fullGcsPath);
    const [exists] = await file.exists();

    if (!exists) {
      console.error(`[GET /api/images] File does not exist in GCS at path: ${fullGcsPath}, though metadata exists.`);
      return NextResponse.json({ error: 'File not found in storage.' }, { status: 404 });
    }

    // Get a readable stream from GCS (this is a Node.js Readable)
    const gcsNodeStream = file.createReadStream();

    // Convert Node.js Readable to Web ReadableStream
    const webReadableStream = Readable.toWeb(gcsNodeStream) as ReadableStream<Uint8Array>; // Node.js 18+

    const headers = new Headers();
    headers.set('Content-Type', imageMetadata.contentType || 'application/octet-stream');
    headers.set('Cache-Control', 'private, max-age=3600');

    return new NextResponse(webReadableStream, { // Use the converted Web ReadableStream
      status: 200,
      headers: headers,
    });

  } catch (error) {
    console.error(`[GET /api/images] Error serving image ${fullGcsPath}:`, error);
    return NextResponse.json({ error: 'Internal server error while serving image.' }, { status: 500 });
  }
} 