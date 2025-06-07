// some/api/route.ts
import prisma, { prismaReady } from '@/lib/prisma';
import { getSecret } from './gcp';

// Add prisma to the NodeJS global type
declare global {
  var prisma: PrismaClient | undefined;
}

// Function to initialize the database URL.
// In production, it fetches from Secret Manager.
// In development, it uses the environment variable.
const initializeDatabaseUrl = async () => {
  if (process.env.NODE_ENV === 'production') {
    console.log("Production environment detected. Fetching DATABASE_URL from Secret Manager...");
    const secretValue = await getSecret('DATABASE_URL');
    if (secretValue) {
      console.log("Successfully fetched DATABASE_URL from Secret Manager.");
      process.env.DATABASE_URL = secretValue;
    } else {
      console.error("CRITICAL: Failed to fetch DATABASE_URL from Secret Manager. Prisma will fail to initialize.");
      // This will cause Prisma to throw a clear error because the env var is missing.
    }
  } else {
    // In development, we expect DATABASE_URL to be in .env.local
    console.log("Development environment detected. Using DATABASE_URL from environment.");
    if (!process.env.DATABASE_URL) {
        console.error("CRITICAL: DATABASE_URL not found in environment for development. Please set it in your .env.local file.");
    }
  }
};

// Initialize the URL asynchronously. This promise is awaited before the client is created.
const dbUrlPromise = initializeDatabaseUrl();

// PrismaClient is attached to the `global` object in development to prevent
// exhausting your database connection limit.
// See https://pris.ly/d/help/next-js-best-practices
const prisma = global.prisma || new PrismaClient({
    log: ['warn', 'error'],
});

if (process.env.NODE_ENV !== 'production') {
  global.prisma = prisma;
}

// We export the promise to ensure that any part of the app can wait for
// the DB URL to be loaded before trying to use Prisma.
export const prismaReady = dbUrlPromise;
export default prisma;
