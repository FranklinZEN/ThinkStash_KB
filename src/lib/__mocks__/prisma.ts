// src/lib/__mocks__/prisma.ts
import { mockDeep } from 'jest-mock-extended';
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import type { DeepMockProxy } from 'jest-mock-extended'; // Import DeepMockProxy as a type
import { PrismaClient } from '@prisma/client'; // Import the actual type

// Create and export the deep mock
const prismaMock = mockDeep<PrismaClient>();
export default prismaMock;
