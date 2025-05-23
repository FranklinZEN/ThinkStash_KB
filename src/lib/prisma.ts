import { PrismaClient } from '@prisma/client';

// !!!!!!!!!!!!!!!!! LIB/PRISMA.TS - START !!!!!!!!!!!!!!!!!!

let finalDatabaseURL = process.env.DATABASE_URL; // Use existing DATABASE_URL if provided (e.g., from .env.local for dev)

if (!finalDatabaseURL) {
  // Only construct if DATABASE_URL isn't already set (this path for Cloud Run)
  // !!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DATABASE_URL not pre-set, attempting to construct from components for Cloud Run.
  // console.log(
  //   '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DATABASE_URL not pre-set, attempting to construct from components for Cloud Run.',
  // );
  // console.log(
  //   '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_USER:',
  //   process.env.DB_USER,
  // );
  // console.log(
  //   '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_PASSWORD:',
  //   process.env.DB_PASSWORD ? 'Exists' : 'MISSING or empty',
  // );
  // console.log(
  //   '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_NAME:',
  //   process.env.DB_NAME,
  // );
  // console.log(
  //   '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_HOST_PATH:',
  //   process.env.DB_HOST_PATH,
  // );

  if (
    process.env.DB_USER &&
    process.env.DB_PASSWORD &&
    process.env.DB_NAME &&
    process.env.DB_HOST_PATH
  ) {
    // This path is primarily for Cloud Run using the Cloud SQL socket
    finalDatabaseURL = `postgresql://${process.env.DB_USER}:${process.env.DB_PASSWORD}@localhost/${process.env.DB_NAME}?host=${process.env.DB_HOST_PATH}`;
    // !!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Constructed DATABASE_URL (for Cloud Run / socket): ...
    // console.log(
    //   '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Constructed DATABASE_URL (for Cloud Run / socket):',
    //   finalDatabaseURL,
    // );
  } else {
    console.error(
      '[Prisma Client Init] CRITICAL: Missing components (DB_USER, DB_PASSWORD, DB_NAME, DB_HOST_PATH) to construct Cloud SQL DATABASE_URL. Prisma will likely fail. Check Cloud Run secret configuration.',
    );
    finalDatabaseURL =
      'prisma_url_construction_failed_due_to_missing_components_in_cloud_run_env';
  }
} else {
  // !!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Using pre-existing process.env.DATABASE_URL (expected for local dev): ...
  // console.log(
  //   '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Using pre-existing process.env.DATABASE_URL (expected for local dev):',
  //   finalDatabaseURL,
  // );
}

// Ensure Prisma uses the determined URL by setting/overwriting process.env.DATABASE_URL
// This is read by Prisma Client if schema.prisma has url = env("DATABASE_URL")
process.env.DATABASE_URL = finalDatabaseURL;

// !!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Final DATABASE_URL that Prisma will use: ...
// console.log(
//   '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Final DATABASE_URL that Prisma will use:',
//   process.env.DATABASE_URL,
// );
//console.log(
//  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - NODE_ENV:',
//  process.env.NODE_ENV,
//);
// !!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Initializing Prisma Client NOW...
// console.log(
//   '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Initializing Prisma Client NOW...',
// );

// Standard HMR global declaration for prisma
declare global {
  // eslint-disable-next-line no-var
  var prisma: PrismaClient | undefined;
  // eslint-disable-next-line no-var
  var __PRISMA_INSTANCE__: PrismaClient | undefined; // Changed from __PRISMA__
}

const createRealPrismaInstance = () =>
  new PrismaClient({
    log:
      process.env.NODE_ENV === 'development'
        ? ['query', 'info', 'warn', 'error']
        : ['warn', 'error'],
  });

// This is the instance that will be used by default and for HMR
const prismaSingleton = global.prisma ?? createRealPrismaInstance();

// For testing purposes, allow a global override.
// This specific global variable __PRISMA_INSTANCE__ should only be set in test setup.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const testInjectedPrisma = (globalThis as any).__PRISMA_INSTANCE__ as
  | PrismaClient
  | undefined;

// Export the instance: in tests, it's the mock; otherwise, it's the singleton.
// The type exported should always be PrismaClient for build-time analysis.
const prismaExport: PrismaClient = testInjectedPrisma || prismaSingleton;

if (process.env.NODE_ENV !== 'production' && !testInjectedPrisma) {
  // Only set global.prisma for HMR if not in production AND if a test instance isn't already injected
  global.prisma = prismaSingleton; // Ensure the HMR global gets the singleton if no test mock
}

// !!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Prisma Client Initialized (or attempted).
// console.log(
//   '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Prisma Client Initialized (or attempted).',
// );

export default prismaExport;
