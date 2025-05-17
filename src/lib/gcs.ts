import { Storage } from '@google-cloud/storage';
import { v4 as uuidv4 } from 'uuid';

// Initialize the GCS client
const storage = new Storage();
const bucketName = process.env.GCS_MEDIA_BUCKET_NAME || '';

if (!bucketName) {
  throw new Error('GCS_MEDIA_BUCKET_NAME environment variable is not set');
}

const bucket = storage.bucket(bucketName);

export interface UploadedFile {
  url: string;
  filename: string;
  contentType: string;
  size: number;
}

export interface UploadOptions {
  maxSize?: number; // in bytes
  allowedMimeTypes?: string[];
}

const DEFAULT_OPTIONS: UploadOptions = {
  maxSize: 5 * 1024 * 1024, // 5MB
  allowedMimeTypes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
};

export async function uploadFile(
  file: Buffer,
  originalFilename: string,
  contentType: string,
  options: UploadOptions = {},
): Promise<UploadedFile> {
  const mergedOptions = { ...DEFAULT_OPTIONS, ...options };

  // Validate file size
  if (file.length > (mergedOptions.maxSize || 0)) {
    throw new Error(
      `File size exceeds maximum allowed size of ${mergedOptions.maxSize} bytes`,
    );
  }

  // Validate content type
  if (
    mergedOptions.allowedMimeTypes &&
    !mergedOptions.allowedMimeTypes.includes(contentType)
  ) {
    throw new Error(`Content type ${contentType} is not allowed`);
  }

  // Generate a unique filename
  const extension = originalFilename.split('.').pop();
  const filename = `${uuidv4()}.${extension}`;

  // Upload to GCS
  const blob = bucket.file(filename);
  await blob.save(file, {
    metadata: {
      contentType,
    },
  });

  // Make the file publicly accessible - REMOVED due to Uniform Bucket-Level Access
  // await blob.makePublic();

  return {
    url: `https://storage.googleapis.com/${bucketName}/${filename}`,
    filename,
    contentType,
    size: file.length,
  };
}

export async function deleteFile(filename: string): Promise<void> {
  const blob = bucket.file(filename);
  await blob.delete();
}

export async function getSignedUrl(
  filename: string,
  expiresInSeconds = 3600,
): Promise<string> {
  const blob = bucket.file(filename);
  const [url] = await blob.getSignedUrl({
    version: 'v4',
    action: 'read',
    expires: Date.now() + expiresInSeconds * 1000,
  });
  return url;
}
