import { Storage } from '@google-cloud/storage';
import { v4 as uuidv4 } from 'uuid';

export type GCSOptions = { projectId?: string };

export function createGcsClient(opts: GCSOptions = {}): Storage {
  return new Storage(opts);
}

export function getBucket() {
  const storageClient = createGcsClient();
  const bucketName = process.env.GCS_BUCKET_NAME;
  if (!bucketName) {
    if (process.env.NODE_ENV === 'production' && !process.env.NEXT_RUNTIME) {
      console.warn(
        'Build-time warning: GCS_BUCKET_NAME is not set. This is expected during build unless performing GCS operations.',
      );
    } else {
      throw new Error(
        'GCS_BUCKET_NAME environment variable is not set at runtime',
      );
    }
  }
  return storageClient.bucket(
    bucketName || 'dummy-bucket-for-build-type-checking',
  );
}

export interface UploadedFile {
  url: string;
  filename: string; // This should be the GCS path/filename
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
  const bucket = getBucket();
  const bucketName = process.env.GCS_BUCKET_NAME; // Still needed for constructing full paths if necessary, or can be removed if `bucket` object is enough
  if (!bucketName) throw new Error('GCS_BUCKET_NAME not set for uploadFile');

  const mergedOptions = { ...DEFAULT_OPTIONS, ...options };

  if (file.length > (mergedOptions.maxSize || 0)) {
    throw new Error(
      `File size exceeds maximum allowed size of ${mergedOptions.maxSize} bytes`,
    );
  }

  if (
    mergedOptions.allowedMimeTypes &&
    !mergedOptions.allowedMimeTypes.includes(contentType)
  ) {
    throw new Error(`Content type ${contentType} is not allowed`);
  }

  const extension = originalFilename.split('.').pop() || 'bin';
  const gcsFilename = `${uuidv4()}.${extension}`;

  const blob = bucket.file(gcsFilename);
  await blob.save(file, {
    metadata: {
      contentType,
    },
  });
  console.log(`[gcs] File successfully uploaded. Bucket: ${bucket.name}, Path: ${gcsFilename}, ContentType: ${contentType}, Size: ${file.length} bytes`);

  const signedUrl = await getSignedUrl(gcsFilename, 15 * 60);

  return {
    url: signedUrl,
    filename: gcsFilename, // This is the name within the bucket, used as gcsPath
    contentType,
    size: file.length,
  };
}

export async function deleteFile(filename: string): Promise<void> {
  const bucket = getBucket();
  const blob = bucket.file(filename);
  await blob.delete();
}

export async function getSignedUrl(
  filename: string,
  expiresInSeconds = 3600,
): Promise<string> {
  const bucket = getBucket();
  const blob = bucket.file(filename);
  const [url] = await blob.getSignedUrl({
    version: 'v4',
    action: 'read',
    expires: Date.now() + expiresInSeconds * 1000,
  });
  return url;
}

/**
 * Returns the direct GCS storage object path (gsutil URI).
 * This URL is typically used for backend operations or integration with other GCP services,
 * not for direct client-side access if the bucket is private.
 * @param filename The name of the file in the bucket.
 * @returns The GCS object path, e.g., gs://your-bucket-name/your-file.jpg
 */
export function getStorageObjectPath(filename: string): string {
  const bucketName = process.env.GCS_BUCKET_NAME;
  if (!bucketName) {
    // This might be called in contexts where an error is not ideal,
    // but the bucket name is essential.
    console.error(
      'GCS_BUCKET_NAME environment variable is not set when calling getStorageObjectPath',
    );
    // Depending on strictness, could throw an error or return a placeholder/empty string.
    // For now, returning a string that indicates the issue.
    return `gs://[GCS_BUCKET_NAME_NOT_SET]/${filename}`;
  }
  return `gs://${bucketName}/${filename}`;
}
