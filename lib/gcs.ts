import { Storage } from '@google-cloud/storage';
import { Readable } from 'stream';

let storage: Storage;

// On Cloud Run, the library automatically uses the service account
// associated with the Cloud Run instance if GOOGLE_APPLICATION_CREDENTIALS
// is not explicitly set in the environment.
// For local development, you must set the GOOGLE_APPLICATION_CREDENTIALS
// environment variable to the path of your service account key JSON file.
// Make sure this key file is NOT committed to your repository (add it to .gitignore).
if (process.env.NODE_ENV === 'production') {
  storage = new Storage();
} else {
  // Ensure GOOGLE_APPLICATION_CREDENTIALS is set for local development
  if (!process.env.GOOGLE_APPLICATION_CREDENTIALS) {
    console.warn(
      'WARNING: GOOGLE_APPLICATION_CREDENTIALS is not set. ' +
      'GCS operations will likely fail in local development. ' +
      'Ensure it points to your service account key JSON file.'
    );
    // Potentially throw an error or use a mock storage for local dev without credentials
  }
  storage = new Storage();
}

export const bucketName = process.env.GCS_MEDIA_BUCKET_NAME;

if (!bucketName && process.env.NODE_ENV !== 'test') {
  console.warn(
    'GCS_MEDIA_BUCKET_NAME environment variable is not set. ' +
    'File uploads and serving will likely fail. This should be set to \'thinkstash_media_gcs_bucket\'.'
  );
}

/**
 * Uploads a file buffer to Google Cloud Storage.
 * @param {Buffer} buffer The file buffer to upload.
 * @param {string} destinationGCSPath Destination path in GCS (e.g., 'images/myfile.jpg').
 * @param {string} [contentType] Optional. The MIME type of the file e.g., 'image/jpeg'.
 * @returns {Promise<string>} The GCS path of the uploaded file.
 */
export async function uploadBufferToGCS(
  buffer: Buffer,
  destinationGCSPath: string,
  contentType?: string
): Promise<string> {
  if (!bucketName) {
    throw new Error('GCS bucket name is not configured.');
  }
  if (!storage) {
    throw new Error('GCS client is not initialized.');
  }

  const file = storage.bucket(bucketName).file(destinationGCSPath);

  return new Promise((resolve, reject) => {
    const stream = file.createWriteStream({
      metadata: {
        contentType: contentType, // e.g., 'image/jpeg', 'image/png'
      },
      resumable: false, // Use true for large files if needed
    });

    stream.on('error', (err) => {
      console.error(`Error uploading to GCS [${destinationGCSPath}]:`, err);
      reject(err);
    });

    stream.on('finish', () => {
      resolve(destinationGCSPath);
    });

    stream.end(buffer);
  });
}

/**
 * Generates a readable stream for a file from GCS.
 * Used by your application to serve files.
 * @param {string} gcsPath Path to the file in GCS (e.g., 'images/myfile.jpg').
 * @returns {Promise<Readable | null>} A promise that resolves to a readable stream for the file, or null if the file doesn't exist.
 * @throws {Error} if GCS bucket name is not configured or client not initialized.
 */
export async function getGCSFileStream(gcsPath: string): Promise<Readable | null> {
  if (!bucketName) {
    throw new Error('GCS bucket name is not configured. Ensure GCS_MEDIA_BUCKET_NAME is set.');
  }
  if (!storage) {
    throw new Error('GCS client is not initialized.');
  }

  const file = storage.bucket(bucketName).file(gcsPath);
  try {
    const [exists] = await file.exists();
    if (!exists) {
      console.warn(`[gcs.ts] getGCSFileStream - File does not exist at path: ${gcsPath}`);
      return null;
    }
    return file.createReadStream();
  } catch (error) {
    console.error(`[gcs.ts] getGCSFileStream - Error checking existence or creating stream for ${gcsPath}:`, error);
    return null;
  }
}

// Optional: Function to delete a file from GCS
/**
 * Deletes a file from Google Cloud Storage.
 * @param {string} gcsPath Path to the file in GCS (e.g., 'images/myfile.jpg').
 * @returns {Promise<void>}
 */
export async function deleteGCSFile(gcsPath: string): Promise<void> {
  if (!bucketName) {
    throw new Error('GCS bucket name is not configured.');
  }
  if (!storage) {
    throw new Error('GCS client is not initialized.');
  }
  try {
    await storage.bucket(bucketName).file(gcsPath).delete();
  } catch (error) {
    console.error(`Error deleting GCS file ${bucketName}/${gcsPath}:`, error);
    if (error && typeof error === 'object' && 'code' in error && (error as { code: unknown }).code === 404) {
      console.warn(`File not found during deletion (already deleted or never existed): ${bucketName}/${gcsPath}`);
      return;
    }
    throw error; 
  }
} 