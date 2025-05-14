// jest.setup.backend.mjs (ESM version - Plain JavaScript)
import { jest, beforeEach } from '@jest/globals';
import { mockDeep, mockReset } from 'jest-mock-extended';

const prismaMockInstance = mockDeep();

// Mock the $transaction method on the initial instance
prismaMockInstance.$transaction.mockImplementation(async (callback) => {
  return await callback(prismaMockInstance);
});

jest.mock('@/lib/prisma', () => ({
  __esModule: true, // Important for ESM mocks
  // Use a getter to ensure the most current instance is always returned
  get default() {
    return prismaMockInstance;
  }
}));

beforeEach(() => {
  mockReset(prismaMockInstance); // Reset the entire deep mock

  // Re-apply $transaction mock as mockReset might clear it (or if it was on prototype)
  prismaMockInstance.$transaction.mockImplementation(async (callback) => {
    return await callback(prismaMockInstance);
  });
});

// No explicit export needed as jest.mock and beforeEach operate globally for the setup file. 