// jest.setup.backend.mjs (ESM version - Plain JavaScript)
import { jest, beforeEach } from '@jest/globals';
import { mockDeep, mockReset } from 'jest-mock-extended';

const prismaMockInstance = mockDeep();

// Initial mock of $transaction - might be overwritten by beforeEach, but good to have a base
prismaMockInstance.$transaction.mockImplementation(async (callback) => {
  return await callback(prismaMockInstance);
});

// Initial setup of model properties. These will be replaced in beforeEach.
prismaMockInstance.folder = mockDeep();
prismaMockInstance.knowledgeCard = mockDeep();

jest.mock('@/lib/prisma', () => ({
  __esModule: true, // Important for ESM mocks
  // Use a getter to ensure the most current instance is always returned
  get default() {
    return prismaMockInstance;
  }
}));

beforeEach(() => {
  mockReset(prismaMockInstance); // Reset the entire deep mock instance first.

  // Explicitly re-assign model properties to be new deep mocks after reset.
  prismaMockInstance.folder = mockDeep();
  prismaMockInstance.knowledgeCard = mockDeep();
  // Add other models as needed, e.g.:
  // prismaMockInstance.user = mockDeep();
  // prismaMockInstance.tag = mockDeep();

  // Re-apply $transaction mock as it would have been cleared by mockReset on parent
  prismaMockInstance.$transaction.mockImplementation(async (callback) => {
    return await callback(prismaMockInstance);
  });
});

// No explicit export needed as jest.mock and beforeEach operate globally for the setup file. 