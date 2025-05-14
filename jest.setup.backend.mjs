// jest.setup.backend.mjs (ESM version - Plain JavaScript)
import { jest, beforeEach } from '@jest/globals';
import { mockDeep, mockReset } from 'jest-mock-extended';

const prismaMock = mockDeep();

// Mock the $transaction method
prismaMock.$transaction.mockImplementation(async (callback) => {
  return await callback(prismaMock);
});

jest.mock('@/lib/prisma', () => ({
  __esModule: true, // Important for ESM mocks
  default: prismaMock,
}));

beforeEach(() => {
  mockReset(prismaMock);

  // Re-set the $transaction implementation as mockReset might clear it
  prismaMock.$transaction.mockImplementation(async (callback) => {
    return await callback(prismaMock);
  });
});

// No explicit export needed as jest.mock and beforeEach operate globally for the setup file. 