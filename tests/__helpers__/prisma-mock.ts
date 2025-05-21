// tests/__helpers__/prisma-mock.ts
import { PrismaClient } from '@prisma/client';
import { mockDeep, mockReset, DeepMockProxy } from 'jest-mock-extended';

// Create and export the deep mock for PrismaClient
export const prismaMock = mockDeep<PrismaClient>();

// Ensure a clean slate for each test file that might use this mock
beforeEach(() => {
  mockReset(prismaMock);
}); 