import { PrismaClient } from '@prisma/client';

// Declare a global variable to hold the PrismaClient instance
declare global {
  // eslint-disable-next-line no-var
  var prisma: PrismaClient | undefined;
}

// Instantiate PrismaClient, reusing the instance in development
export const prisma = globalThis.prisma || new PrismaClient({
  // Uncomment below to log Prisma queries (useful for debugging)
  // log: ['query', 'info', 'warn', 'error'],
});

// In development, assign the instance to the global variable
if (process.env.NODE_ENV !== 'production') {
  globalThis.prisma = prisma;
} 