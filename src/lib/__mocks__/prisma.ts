import { mockDeep, DeepMockProxy as _DeepMockProxy } from 'jest-mock-extended';
import { PrismaClient } from '@prisma/client';

// This is the type of the actual PrismaClient if we were importing it directly for typing
// However, for mocking, we just need to mock the shape that the application uses.
// The tests import prismaActualForTyping from '@/lib/prisma' for this purpose.

// Create and export the deep mock instance.
// Jest will automatically use this when jest.mock('@/lib/prisma') is called,
// or if this file is placed correctly in a __mocks__ directory.
const mockPrismaClient = mockDeep<PrismaClient>();

export default mockPrismaClient; 