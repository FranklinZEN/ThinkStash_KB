import { Storage } from '@google-cloud/storage';
import { v4 as uuidv4 } from 'uuid';

// Initialize the GCS client
const storage = new Storage();

// Helper function to get the bucket and ensure bucketName is set at runtime
function getBucket() {
  const bucketName = process.env.GCS_MEDIA_BUCKET_NAME;
  if (!bucketName) {
    // Log a warning during build, but throw error only if this function is somehow called during build for a real operation
    if (process.env.NODE_ENV === 'production' && !process.env.NEXT_RUNTIME) {
      // NEXT_RUNTIME check can help differentiate build vs. server runtime in some cases
      console.warn(
        'Build-time warning: GCS_MEDIA_BUCKET_NAME is not set. This is expected during build unless performing GCS operations.',
      );
      // For build, we might need to return a dummy/mock bucket or handle it differently if functions are invoked.
      // However, the goal is to prevent throwing an error just on module import.
      // Returning a placeholder or allowing it to proceed and fail later if a function is called during build is one strategy.
      // For now, we'll let it pass here and rely on runtime checks in functions.
    } else {
      // This error will be thrown if a GCS operation is attempted at runtime without the env var.
      throw new Error(
        'GCS_MEDIA_BUCKET_NAME environment variable is not set at runtime',
      );
    }
  }
  return storage.bucket(bucketName || 'dummy-bucket-for-build-type-checking'); // Provide a fallback for type-checking if bucketName is falsy during build
}

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
  const bucket = getBucket(); // Get bucket at runtime
  const bucketName = process.env.GCS_MEDIA_BUCKET_NAME;
  if (!bucketName)
    throw new Error('GCS_MEDIA_BUCKET_NAME not set for uploadFile');

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
  const bucket = getBucket(); // Get bucket at runtime
  const blob = bucket.file(filename);
  await blob.delete();
}

export async function getSignedUrl(
  filename: string,
  expiresInSeconds = 3600,
): Promise<string> {
  const bucket = getBucket(); // Get bucket at runtime
  const blob = bucket.file(filename);
  const [url] = await blob.getSignedUrl({
    version: 'v4',
    action: 'read',
    expires: Date.now() + expiresInSeconds * 1000,
  });
  return url;
}
