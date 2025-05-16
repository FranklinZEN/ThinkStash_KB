import { PrismaClient } from '@prisma/client';

// Log environment variables at the beginning of the file
console.log('!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - START !!!!!!!!!!!!!!!!!!');
console.log('!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_USER:', process.env.DB_USER);
console.log(
  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_PASSWORD:',
  process.env.DB_PASSWORD ? 'Exists' : 'MISSING or empty',
);
console.log('!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_NAME:', process.env.DB_NAME);
console.log(
  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - DB_HOST_PATH:',
  process.env.DB_HOST_PATH,
);

let databaseURL;
if (
  process.env.DB_USER &&
  process.env.DB_PASSWORD &&
  process.env.DB_NAME &&
  process.env.DB_HOST_PATH
) {
  databaseURL = `postgresql://${process.env.DB_USER}:${process.env.DB_PASSWORD}@localhost/${process.env.DB_NAME}?host=${process.env.DB_HOST_PATH}`;
  console.log(
    '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Constructed DATABASE_URL:',
    databaseURL,
  );
} else {
  console.error(
    '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Missing one or more DB env vars for DATABASE_URL construction. Check Cloud Run secret config. DB_USER:',
    process.env.DB_USER,
    'DB_NAME:',
    process.env.DB_NAME,
    'DB_HOST_PATH:',
    process.env.DB_HOST_PATH,
    'DB_PASSWORD_EXISTS:',
    !!process.env.DB_PASSWORD,
  );
  databaseURL = 'prisma_url_construction_failed_due_to_missing_parts';
}
// Ensure DATABASE_URL is set for Prisma, as schema.prisma likely uses env("DATABASE_URL")
process.env.DATABASE_URL = databaseURL;

console.log(
  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Final DATABASE_URL for Prisma init:',
  process.env.DATABASE_URL,
);
console.log(
  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - NODE_ENV:',
  process.env.NODE_ENV,
);
console.log(
  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Initializing Prisma Client NOW...',
);

// Declare a global variable to hold the PrismaClient instance
declare global {
  // allow global `var` declarations
  // eslint-disable-next-line no-var
  var prisma: PrismaClient | undefined;
}

// Instantiate PrismaClient, reusing the instance in development
const prisma =
  global.prisma ||
  new PrismaClient({
    // Log Prisma queries (useful for debugging)
    log: ['query', 'info', 'warn', 'error'],
  });

// In development, assign the instance to the global variable
if (process.env.NODE_ENV !== 'production') global.prisma = prisma;

console.log(
  '!!!!!!!!!!!!!!!!! LIB/PRISMA.TS - Prisma Client Initialized (or attempted).',
);

export default prisma;
