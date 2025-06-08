import { PrismaClient } from '@prisma/client';

console.log('!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - START !!!!!!!!!!!!!!!!!!');
console.log(
  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Initial process.env.DATABASE_URL:',
  process.env.DATABASE_URL,
); // Log initial

let finalDatabaseURL = process.env.DATABASE_URL; // Use existing DATABASE_URL if provided (e.g., from .env.local for dev)

if (!finalDatabaseURL) {
  // Only construct if DATABASE_URL isn't already set (this path for Cloud Run)
  console.log(
    '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DATABASE_URL not pre-set, attempting to construct from components for Cloud Run.',
  );
  console.log(
    '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_USER:',
    process.env.DB_USER,
  );
  console.log(
    '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_PASSWORD:',
    process.env.DB_PASSWORD ? 'Exists' : 'MISSING or empty',
  );
  console.log(
    '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_NAME:',
    process.env.DB_NAME,
  );
  console.log(
    '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_HOST_PATH:',
    process.env.DB_HOST_PATH,
  );

  if (
    process.env.DB_USER &&
    process.env.DB_PASSWORD &&
    process.env.DB_NAME &&
    process.env.DB_HOST_PATH
  ) {
    // This path is primarily for Cloud Run using the Cloud SQL socket
    finalDatabaseURL = `postgresql://${process.env.DB_USER}:${process.env.DB_PASSWORD}@localhost/${process.env.DB_NAME}?host=${process.env.DB_HOST_PATH}`;
    console.log(
      '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Constructed DATABASE_URL (for Cloud Run / socket):',
      finalDatabaseURL,
    );
  } else {
    console.error(
      '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - CRITICAL: Missing components (DB_USER, etc.) to construct Cloud SQL DATABASE_URL. Prisma will likely fail. Check Cloud Run secret configuration.',
    );
    finalDatabaseURL =
      'prisma_url_construction_failed_due_to_missing_components_in_cloud_run_env';
  }
} else {
  console.log(
    '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Using pre-existing process.env.DATABASE_URL (expected for local dev):',
    finalDatabaseURL,
  );
}

// Ensure Prisma uses the determined URL by setting/overwriting process.env.DATABASE_URL
// This is read by Prisma Client if schema.prisma has url = env("DATABASE_URL")
process.env.DATABASE_URL = finalDatabaseURL;

console.log(
  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Final DATABASE_URL that Prisma will use:',
  process.env.DATABASE_URL,
);
console.log(
  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - NODE_ENV:',
  process.env.NODE_ENV,
);
console.log(
  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Initializing Prisma Client NOW...',
);

declare global {
  /* eslint-disable no-var */
  var prisma: PrismaClient | undefined;
  /* eslint-enable no-var */
}

const prisma =
  global.prisma ||
  new PrismaClient({
    log: ['warn', 'error'], // Adjusted logging for production, was: ['query', 'info', 'warn', 'error']
  });

if (process.env.NODE_ENV !== 'production') {
  global.prisma = prisma;
}

console.log(
  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Prisma Client Initialized (or attempted).',
);

export default prisma;
