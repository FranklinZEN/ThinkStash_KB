import { createMockedPrismaClient } from './helpers/apiTestSetup'; // Adjust path as necessary

// console.log('[vitest.globalSetup.ts] Setting up global Prisma mock via __PRISMA__ global variable.');

const mockedPrisma = createMockedPrismaClient();
(globalThis as any).__PRISMA__ = mockedPrisma;

// console.log('[vitest.globalSetup.ts] Global __PRISMA__ has been set.');

// The actual vi.mock('@/lib/prisma', ...) has been removed from here,
// as the injection pattern relies on modifying src/lib/prisma.ts directly. 