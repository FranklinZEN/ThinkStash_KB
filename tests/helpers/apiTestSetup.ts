import { vi, Mock } from 'vitest';
import { PrismaClient } from '@prisma/client'; // Import the actual type

// ---- Mock User ----
// As per the refactoring plan, a shared MOCK_USER_ID
export const MOCK_USER_ID = 'clmockuser1234567890'; // Replace with a suitable generic ID if needed

// ---- Prisma Mock Functions ----
// These are exported so that test files can import them to set mock implementations
// and make assertions. The actual vi.mock call that USES these will be in a global setup file.
export const mockFolderFindMany: Mock = vi.fn();
export const mockFolderCreate: Mock = vi.fn();
export const mockFolderFindUnique: Mock = vi.fn();
export const mockFolderDeleteMany: Mock = vi.fn();
export const mockFolderUpdate: Mock = vi.fn();
export const mockFolderDelete: Mock = vi.fn();       // For prisma.folder.delete
export const mockFolderUpdateMany: Mock = vi.fn();   // For prisma.folder.updateMany
// Note: mockFolderUpdate was not a vi.fn() in the original local mock, actual was used.

// User mocks, based on original route.test.ts local mocks
export const mockUserDeleteMany: Mock = vi.fn();
export const mockUserCreate: Mock = vi.fn();
export const mockUserFindUnique: Mock = vi.fn();
// Note: mockUserFindUnique was not a vi.fn() in the original local mock, actual was used.

// todo: Add other common mocks as per refactoring plan (e.g., ImageRecord, GCS)
// export const mockImageRecordCreate: Mock = vi.fn();
// export const mockImageRecordFindUnique: Mock = vi.fn();

// Add for knowledgeCard model
export const mockKnowledgeCardUpdateMany: Mock = vi.fn();
export const mockKnowledgeCardDeleteMany: Mock = vi.fn(); // If needed
// ... other knowledgeCard mock fns if needed ...

// The vi.mock('@/lib/prisma', ...) call has been moved to tests/vitest.globalSetup.ts
// This file (apiTestSetup.ts) now only exports the mock functions and constants.

// Reminder: tests/vitest.globalSetup.ts should be configured in vitest.config.ts
// to ensure the Prisma mock is applied globally before tests run.

// ---- Factory for the Mocked Prisma Client ----
// This function creates the object that will be globally injected.
export function createMockedPrismaClient(): PrismaClient {
  // It's important to return an object that structurally matches PrismaClient
  // as much as possible, especially for parts not being deeply mocked.
  // We can use a cast to PrismaClient for type safety here.

  const actualPrismaClientPrototype = PrismaClient.prototype;

  const mockedClient = {
    // Spread some base properties or use a minimal mock if preferred
    // For a full DI swap, it's often enough to mock just the model delegates used.
    $connect: vi.fn().mockResolvedValue(undefined),
    $disconnect: vi.fn().mockResolvedValue(undefined),
    $on: vi.fn(),
    $use: vi.fn(),
    $executeRaw: vi.fn(),
    $executeRawUnsafe: vi.fn(),
    $queryRaw: vi.fn(),
    $queryRawUnsafe: vi.fn(),
    $transaction: vi.fn().mockImplementation(async (arg: any) => {
      if (typeof arg === 'function') {
        // If it's a function, invoke it with the mock client itself (or a specific mock transaction API)
        return await arg(mockedClient); 
      }
      // If it's an array of operations (batch transaction)
      // This is a simplified mock; real batch transactions might need more detailed handling
      // For many tests, ensuring it doesn't break and operations are called is enough.
      // Here, we'll assume individual operations are mocked and will be called.
      const results = [];
      for (const op of arg) {
        // This part is tricky without knowing what 'op' is. 
        // Prisma operations aren't directly executable like this.
        // For robust $transaction mocking with arrays, specific test setup for inner operations is better.
        // results.push(await op); // This line is problematic
      }
      return results; 
    }),

    // --- Mocked Models ---
    folder: {
      // It's good practice to ensure all methods from the actual model delegate are present,
      // either as mocks or by carefully taking from the actual prototype if safe.
      // For now, only mocking what tests require based on current usage.
      findMany: mockFolderFindMany,
      create: mockFolderCreate,
      findUnique: mockFolderFindUnique,
      deleteMany: mockFolderDeleteMany,
      update: mockFolderUpdate,
      delete: mockFolderDelete,           // Added
      updateMany: mockFolderUpdateMany,   // Added
      upsert: vi.fn(),
      count: vi.fn(),
      aggregate: vi.fn(),
      groupBy: vi.fn(),
      findFirst: vi.fn(),
      findFirstOrThrow: vi.fn(),
      findUniqueOrThrow: vi.fn(),
      // Add other folder methods as vi.fn() if they get used by the SUT, e.g.:
      // update: vi.fn(),
      // upsert: vi.fn(),
      // Aggregate, count, etc. would also go here if needed.
    },
    user: {
      findMany: vi.fn(),
      create: mockUserCreate,
      findUnique: mockUserFindUnique,
      deleteMany: mockUserDeleteMany,
      update: vi.fn(),
      upsert: vi.fn(),
      delete: vi.fn(),
      count: vi.fn(),
      aggregate: vi.fn(),
      groupBy: vi.fn(),
      findFirst: vi.fn(),
      findFirstOrThrow: vi.fn(),
      findUniqueOrThrow: vi.fn(),
    },
    knowledgeCard: { // Add knowledgeCard delegate
      updateMany: mockKnowledgeCardUpdateMany,
      deleteMany: mockKnowledgeCardDeleteMany, // if used
      // Add all other methods for knowledgeCard as vi.fn() for completeness
      create: vi.fn(),
      findUnique: vi.fn(),
      findMany: vi.fn(),
      update: vi.fn(),
      upsert: vi.fn(),
      delete: vi.fn(), 
      count: vi.fn(),
      aggregate: vi.fn(),
      groupBy: vi.fn(),
      findFirst: vi.fn(),
      findFirstOrThrow: vi.fn(),
      findUniqueOrThrow: vi.fn(),
    },
    // Ensure other models used by the application are at least present, even if not deeply mocked.
    // A simple way for unmocked models is to make them objects with vi.fn() for all methods.
    // Example: if you have an 'imageRecord' model:
    // imageRecord: {
    //   create: vi.fn(),
    //   findUnique: vi.fn(),
    //   findMany: vi.fn(),
    //   // ... etc. for all imageRecord methods used
    // },

    // Cast to PrismaClient to satisfy type requirements.
    // This is a shallow mock; deeper properties/methods of actualPrismaClientPrototype
    // are not automatically included unless explicitly added above.
  } as unknown as PrismaClient;

  // To make it more robust for methods not explicitly mocked on delegates:
  // One could dynamically assign vi.fn() to any method on actualPrismaClient.folder (etc.)
  // that isn't one of our explicit mocks. For now, this explicit list is safer.

  return mockedClient;
} 