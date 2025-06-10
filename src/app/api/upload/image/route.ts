import { NextRequest, NextResponse } from 'next/server';
import { uploadFile } from '@/lib/gcs';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

// Define constants for validation
const ALLOWED_MIME_TYPES = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
];
const MAX_FILE_SIZE_MB = 5; // 5MB
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

export async function POST(request: NextRequest) {
  console.log('[/api/upload/image] POST request received');
  try {
    // Check authentication
    console.log('Checking session...');
    const session = await getServerSession(authOptions);
    if (!session) {
      console.error('[/api/upload/image] Unauthorized: No session found');
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    console.log(
      '[/api/upload/image] Session valid for user:',
      session.user?.email,
    );

    // Get the form data
    console.log('[/api/upload/image] Parsing form data...');
    const formData = await request.formData();
    const file = formData.get('file') as File;

    if (!file) {
      console.error('[/api/upload/image] No file provided in form data');
      return NextResponse.json({ error: 'No file provided' }, { status: 400 });
    }
    console.log(
      `[/api/upload/image] File received: ${file.name}, type: ${file.type}, size: ${file.size}`,
    );

    // Validate MIME type
    if (!ALLOWED_MIME_TYPES.includes(file.type)) {
      console.error(
        `[/api/upload/image] Invalid file type: ${file.type}. Allowed: ${ALLOWED_MIME_TYPES.join(', ')}`,
      );
      return NextResponse.json(
        {
          error: `Invalid file type. Allowed types are: ${ALLOWED_MIME_TYPES.join(', ')}.`,
        },
        { status: 400 },
      );
    }

    // Validate file size
    if (file.size > MAX_FILE_SIZE_BYTES) {
      console.error(
        `[/api/upload/image] File too large: ${file.size} bytes. Max size: ${MAX_FILE_SIZE_BYTES} bytes.`,
      );
      return NextResponse.json(
        { error: `File exceeds maximum size of ${MAX_FILE_SIZE_MB}MB.` },
        { status: 400 },
      );
    }

    // Convert File to Buffer
    console.log('[/api/upload/image] Converting file to buffer...');
    const buffer = Buffer.from(await file.arrayBuffer());
    console.log(
      '[/api/upload/image] File converted to buffer, length:',
      buffer.length,
    );

    // Upload to GCS
    console.log(`[/api/upload/image] Calling uploadFile for ${file.name}...`);
    const result = await uploadFile(buffer, file.name, file.type);
    console.log('[/api/upload/image] uploadFile result:', result);

    return NextResponse.json(result);
  } catch (error) {
    console.error(
      '[/api/upload/image] Error during file upload process:',
      error,
    );
    // Check if error is an object and has a message property
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    return NextResponse.json(
      { error: 'Failed to upload file', details: errorMessage },
      { status: 500 },
    );
  }
}

// Configure the API route to accept multipart/form-data
/*
export const config = {
  api: {
    bodyParser: false,
  },
};
*/
