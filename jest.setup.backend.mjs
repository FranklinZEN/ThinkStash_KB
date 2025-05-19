// jest.setup.backend.mjs
import { beforeEach } from '@jest/globals';
import { mockReset } from 'jest-mock-extended';
import prismaMockInstance from '@/lib/prisma'; // This imports the mock via moduleNameMapper

console.log('####### jest.setup.backend.mjs: EXECUTING with Prisma mock reset #######');

beforeEach(() => {
  // console.log('jest.setup.backend.mjs: Resetting prismaMockInstance'); // Optional diagnostic
  mockReset(prismaMockInstance); // Reset the globally mocked Prisma instance
}); 