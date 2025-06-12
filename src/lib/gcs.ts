import { Storage } from '@google-cloud/storage';

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
  filename: string; // This is the GCS path/filename
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
  gcsFilename: string,
  contentType: string,
  options: UploadOptions = {},
): Promise<Omit<UploadedFile, 'url'>> {
  const bucket = getBucket();
  const bucketName = process.env.GCS_BUCKET_NAME;
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

  const blob = bucket.file(gcsFilename);
  await blob.save(file, {
    metadata: {
      contentType,
    },
    public: true,
  });
  console.log(
    `[gcs] File successfully uploaded and made public. Bucket: ${
      bucket.name
    }, Path: ${gcsFilename}, ContentType: ${contentType}, Size: ${
      file.length
    } bytes`,
  );

  return {
    filename: gcsFilename,
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
 * Returns the public URL for a file in the GCS bucket.
 * This assumes the file has been made public via `uploadFile`.
 * @param filename The name of the file in the bucket.
 * @returns The public URL, e.g., https://storage.googleapis.com/your-bucket-name/your-file.jpg
 */
export function getPublicUrl(filename: string): string {
  const bucketName = process.env.GCS_BUCKET_NAME;
  if (!bucketName) {
    console.error(
      'GCS_BUCKET_NAME environment variable is not set when calling getPublicUrl',
    );
    return `https://storage.googleapis.com/[GCS_BUCKET_NAME_NOT_SET]/${filename}`;
  }
  return `https://storage.googleapis.com/${bucketName}/${filename}`;
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
