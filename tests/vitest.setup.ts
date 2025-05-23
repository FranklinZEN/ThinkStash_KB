// tests/vitest.setup.ts
import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';
import { server as mswServer } from '@/mocks/server'; // Assuming src/mocks/server.ts exports 'server'
import type { PrismaClient } from '@prisma/client'; // Import PrismaClient
import {
    createMockedPrismaClient, // Import the main factory
    mockFolderFindMany, mockFolderCreate, mockFolderFindUnique, mockFolderDeleteMany, mockFolderUpdate, mockFolderDelete, mockFolderUpdateMany,
    mockUserDeleteMany, mockUserCreate, mockUserFindUnique,
    mockImageRecordCreate, mockImageRecordFindUnique, mockImageRecordUpdate, mockImageRecordDeleteMany,
    mockKnowledgeCardUpdateMany, mockKnowledgeCardDeleteMany,
    mockGCSUploadFile, mockGetSignedUrlForImageGCS
} from './helpers/apiTestSetup';
import { Readable } from 'stream';

console.log('[vitest.setup.ts] Initializing global __PRISMA_INSTANCE__ mock...');
(globalThis as any).__PRISMA_INSTANCE__ = createMockedPrismaClient();
console.log('[vitest.setup.ts] Global __PRISMA_INSTANCE__ mock initialized.');

// ---- GCS Mocking ----
// Centralized mock for the GCS utility module, using functions from apiTestSetup
// This runs in the correct Vitest context (before each test file).
console.log('[vitest.setup.ts] Setting up vi.mock for @/lib/gcs...');
vi.mock('@/lib/gcs', () => ({
  __esModule: true,
  uploadFile: mockGCSUploadFile,
  getSignedUrlForImageGCS: mockGetSignedUrlForImageGCS,
  getBucket: vi.fn(() => ({
    file: vi.fn(() => ({
      exists: vi.fn().mockResolvedValue([true]),
      createReadStream: vi.fn(() => {
        const readable = new Readable();
        readable._read = () => {};
        process.nextTick(() => readable.push(null));
        return readable;
      }),
    })),
  })),
}));
console.log('[vitest.setup.ts] vi.mock for @/lib/gcs configured.');

declare global {
    // eslint-disable-next-line no-var
    var __PRISMA_INSTANCE__: PrismaClient | undefined; // Corrected type
    // No __TEST_SERVER_URL__ global needed here for this strategy
}

// MSW setup: Start the server before all tests
// Note: MSW setup's beforeAll/afterAll will apply to each test file's scope.
// If truly global MSW listening is needed (once per Vitest run), it's more complex.
// However, for resetting handlers, this is standard.
beforeAll(() => {
  console.log('[vitest.setup.ts] MSW mswServer.listen() called for a test file.');
  mswServer.listen({ onUnhandledRequest: 'bypass' });
});

// Reset any request handlers that may be added during the tests,
// so they don't affect other tests.
afterEach(() => {
  // console.log('[vitest.setup.ts] MSW server.resetHandlers() called after a test.');
  mswServer.resetHandlers();
});

// Clean up after the tests are finished.
afterAll(() => {
  console.log('[vitest.setup.ts] MSW mswServer.close() called after a test file.');
  mswServer.close();
});

// The Prisma middleware logging has been removed as it might interfere with the
// global Prisma mocking strategy and is not part of the core test setup.

// All other global mocks (sessionUtils, services) should be handled by their respective
// mocking strategies outlined in the V4 plan (e.g., global injection for Prisma, 
// header-based auth for API tests, or specific vi.mock calls where appropriate).