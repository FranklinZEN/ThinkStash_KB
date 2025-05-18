import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path to your authOptions
import { Storage } from '@google-cloud/storage';
import { v4 as uuidv4 } from 'uuid';
import prisma from '@/lib/prisma'; // Adjust path to your Prisma client

// Define and export the UploadApiResponse type
export interface UploadApiResponse {
  gcsPath: string;
  appServedUrl: string;
  contentType: string;
  originalFilename: string;
  size: number;
  userId: string;
}

const GCS_MEDIA_BUCKET_NAME = process.env.GCS_MEDIA_BUCKET_NAME;

if (!GCS_MEDIA_BUCKET_NAME) {
  console.error('GCS_MEDIA_BUCKET_NAME environment variable is not set.');
  // Depending on your error handling strategy, you might throw an error here
  // or ensure this is caught and handled gracefully during startup or request time.
}

// Initialize GCS Storage client
// Ensure GOOGLE_APPLICATION_CREDENTIALS is set in your environment for this to work locally/on GCP.
const storage = new Storage();
const bucket = GCS_MEDIA_BUCKET_NAME ? storage.bucket(GCS_MEDIA_BUCKET_NAME) : null;

export async function POST(req: NextRequest) {
  if (!bucket) {
    return NextResponse.json(
      { error: 'GCS bucket not configured. GCS_MEDIA_BUCKET_NAME is missing.' }, 
      { status: 500 }
    );
  }

  const session = await getServerSession(authOptions);
  if (!session || !session.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  const userId = session.user.id;

  try {
    const formData = await req.formData();
    const file = formData.get('file') as File | null;

    if (!file) {
      return NextResponse.json({ error: 'No file provided.' }, { status: 400 });
    }

    // Generate a unique path/filename for GCS
    const fileExtension = file.name.split('.').pop();
    const uniqueFilename = `${uuidv4()}${fileExtension ? '.' + fileExtension : ''}`;
    const gcsPath = `images/${userId}/${uniqueFilename}`;

    // Upload to GCS
    const gcsFile = bucket.file(gcsPath);
    const stream = gcsFile.createWriteStream({
      metadata: {
        contentType: file.type,
      },
      resumable: false, // simpler for single uploads, consider true for large files with retries
    });

    // Convert ArrayBuffer to Buffer for streaming if needed, or use file.stream()
    const buffer = Buffer.from(await file.arrayBuffer());
    await new Promise((resolve, reject) => {
      stream.on('error', (err) => {
        console.error('GCS Upload Error:', err);
        reject(err);
      });
      stream.on('finish', resolve);
      stream.end(buffer);
    });

    const appServedUrl = `/api/images/${gcsPath}`;

    const metadata: UploadApiResponse = {
      gcsPath,
      appServedUrl,
      contentType: file.type,
      originalFilename: file.name,
      size: file.size,
      userId,
    };

    // Note: We are NOT saving to ImageMetadata table here.
    // That will be done when the card is saved, using the metadata returned by this API.

    return NextResponse.json(metadata, { status: 200 });

  } catch (error) {
    console.error('Image upload failed:', error);
    let errorMessage = 'Image upload failed.';
    if (error instanceof Error) {
      errorMessage = error.message;
    }
    return NextResponse.json({ error: 'Image upload failed', details: errorMessage }, { status: 500 });
  }
}

// The config object for bodyParser: false is not needed for App Router route handlers
// as Next.js handles FormData parsing by default for them.
// If you were using Pages Router (pages/api), you would need it:
// export const config = {
//   api: {
//     bodyParser: false,
//   },
// };
