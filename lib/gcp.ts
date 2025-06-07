import { SecretManagerServiceClient } from '@google-cloud/secret-manager';

const client = new SecretManagerServiceClient();

/**
 * Fetches the value of a secret from Google Cloud Secret Manager.
 * Caches the secret in memory to avoid repeated API calls.
 */
const secretCache = new Map<string, string>();

export async function getSecret(secretName: string): Promise<string | null> {
  if (secretCache.has(secretName)) {
    return secretCache.get(secretName) as string;
  }

  // Ensure the GCP_PROJECT_ID environment variable is set.
  const projectId = process.env.GCP_PROJECT_ID;
  if (!projectId) {
    console.error('GCP_PROJECT_ID environment variable not set.');
    return null;
  }

  try {
    const [version] = await client.accessSecretVersion({
      name: `projects/${projectId}/secrets/${secretName}/versions/latest`,
    });

    const payload = version.payload?.data?.toString();
    if (payload) {
      secretCache.set(secretName, payload);
      return payload;
    }

    console.warn(`Secret ${secretName} has no payload.`);
    return null;
  } catch (error) {
    console.error(`Error accessing secret ${secretName}:`, error);
    return null;
  }
} 