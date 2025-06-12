import { NextRequest, NextResponse } from 'next/server';
import { Storage } from '@google-cloud/storage';
import { v4 as uuidv4 } from 'uuid';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust if your authOptions are elsewhere

const GCS_BUCKET_NAME = process.env.GCS_BUCKET_NAME || 'thinkstash_media_gcs_bucket';

let storage: Storage;
try {
  storage = new Storage();
} catch (e) {
  console.error("Failed to initialize Google Cloud Storage client. Ensure GOOGLE_APPLICATION_CREDENTIALS are set and valid.", e);
  // This is a critical error, uploads will fail.
}

export async function POST(req: NextRequest) {
  if (!storage) {
    console.error('GCS Storage client not initialized. File upload cannot proceed.');
    return NextResponse.json(
      { error: 'Server configuration error for file uploads.' },
      { status: 500 },
    );
  }

  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userId = session.user.id;

    const formData = await req.formData();
    const file = formData.get('file') as File | null;

    if (!file) {
      return NextResponse.json({ error: 'No file provided.' }, { status: 400 });
    }

    // Basic validation (optional, add more as needed)
    if (file.size === 0) {
      return NextResponse.json({ error: 'File is empty.' }, { status: 400 });
    }

    // Generate a unique filename to prevent overwrites and ensure GCS compatibility
    const fileExtension = file.name.split('.').pop();
    const uniqueFilename = `${userId}/${uuidv4()}${fileExtension ? '.' + fileExtension : ''}`;

    const gcsFile = storage.bucket(GCS_BUCKET_NAME).file(uniqueFilename);

    // Stream the file to GCS
    const stream = gcsFile.createWriteStream({
      metadata: {
        contentType: file.type,
        metadata: { // Custom metadata if needed
          originalFilename: file.name,
          userId: userId,
        },
      },
      resumable: false, // Use true for large files if you want resumable uploads
    });

    // Convert File stream to buffer then write to GCS stream
    const fileBuffer = Buffer.from(await file.arrayBuffer());

    await new Promise((resolve, reject) => {
      stream.on('error', (err) => {
        console.error(`Error uploading to GCS: ${err.message}`, err);
        reject(new Error(`Failed to upload file to GCS: ${err.message}`));
      });
      stream.on('finish', () => {
        console.log(`File ${uniqueFilename} uploaded to ${GCS_BUCKET_NAME}.`);
        resolve(true);
      });
      stream.end(fileBuffer);
    });

    const fileId = `gs://${GCS_BUCKET_NAME}/${uniqueFilename}`;

    return NextResponse.json({ 
      message: 'File uploaded successfully', 
      file_id: fileId,
      originalFilename: file.name,
      gcsPath: uniqueFilename // Relative path within bucket
    }, { status: 201 });

  } catch (error) {
    console.error('Error in file upload API route:', error);
    const errorMessage = error instanceof Error ? error.message : 'An unknown error occurred during file upload.';
    return NextResponse.json(
      { error: 'Internal server error during file upload.', details: errorMessage },
      { status: 500 },
    );
  }
} 