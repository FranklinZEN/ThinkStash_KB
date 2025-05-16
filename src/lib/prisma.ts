import { PrismaClient } from '@prisma/client';

// console.log("!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - START !!!!!!!!!!!!!!!!!!"); // Removed
// console.log("!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_USER:", process.env.DB_USER); // Removed
// console.log("!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_PASSWORD:", process.env.DB_PASSWORD ? "Exists" : "MISSING or empty"); // Removed
// console.log("!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_NAME:", process.env.DB_NAME); // Removed
// console.log("!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_HOST_PATH:", process.env.DB_HOST_PATH); // Removed

let databaseURL;
if (
  process.env.DB_USER &&
  process.env.DB_PASSWORD &&
  process.env.DB_NAME &&
  process.env.DB_HOST_PATH
) {
  databaseURL = `postgresql://${process.env.DB_USER}:${process.env.DB_PASSWORD}@localhost/${process.env.DB_NAME}?host=${process.env.DB_HOST_PATH}`;
  // console.log("!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Constructed DATABASE_URL:", databaseURL); // Removed
} else {
  // Keep this critical error log if components for DATABASE_URL are missing
  console.error(
    'CRITICAL: LIB/PRISMA.TS - Missing one or more environment variables for DATABASE_URL construction (DB_USER, DB_PASSWORD, DB_NAME, DB_HOST_PATH). Prisma will likely fail to initialize. Check Cloud Run secret configuration.',
  );
  databaseURL = 'prisma_url_construction_failed_due_to_missing_parts'; // Prisma will error on this
}
process.env.DATABASE_URL = databaseURL;

// console.log("!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Final DATABASE_URL for Prisma init:", process.env.DATABASE_URL); // Removed
// console.log("!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - NODE_ENV:", process.env.NODE_ENV); // Removed
console.log('LIB/PRISMA.TS: Initializing Prisma Client...'); // Simplified log

declare global {
  /* eslint-disable no-var */
  var prisma: PrismaClient | undefined;
  /* eslint-enable no-var */
}

const prisma =
  global.prisma ||
  new PrismaClient({
    // log: ['warn', 'error'], // Recommended for production: only log warnings and errors
  });

if (process.env.NODE_ENV !== 'production') {
  global.prisma = prisma;
}

console.log('LIB/PRISMA.TS: Prisma Client initialized.'); // Simplified log

export default prisma;
