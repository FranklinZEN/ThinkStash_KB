import { vi, Mock } from 'vitest';
import type { PrismaClient } from '@prisma/client';

// ---- Mock User ----
export const MOCK_USER_ID = 'clmockuser1234567890'; 

// ---- Prisma Mock Functions ----
// Folder
export const mockFolderFindMany: Mock = vi.fn();
export const mockFolderCreate: Mock = vi.fn();
export const mockFolderFindUnique: Mock = vi.fn();
export const mockFolderDeleteMany: Mock = vi.fn();
export const mockFolderUpdate: Mock = vi.fn();
export const mockFolderDelete: Mock = vi.fn();
export const mockFolderUpdateMany: Mock = vi.fn();

// User
export const mockUserDeleteMany: Mock = vi.fn();
export const mockUserCreate: Mock = vi.fn();
export const mockUserFindUnique: Mock = vi.fn();

// ImageRecord
export const mockImageRecordCreate: Mock = vi.fn();
export const mockImageRecordFindUnique: Mock = vi.fn();
export const mockImageRecordUpdate: Mock = vi.fn();
export const mockImageRecordDeleteMany: Mock = vi.fn();

// KnowledgeCard (Ensured all relevant operations have specific mocks)
export const mockKnowledgeCardFindUnique: Mock = vi.fn();
export const mockKnowledgeCardFindFirst: Mock = vi.fn(); 
export const mockKnowledgeCardFindMany: Mock = vi.fn();  
export const mockKnowledgeCardCreate: Mock = vi.fn();    
export const mockKnowledgeCardUpdate: Mock = vi.fn();    
export const mockKnowledgeCardDelete: Mock = vi.fn();    
export const mockKnowledgeCardDeleteMany: Mock = vi.fn(); 
export const mockKnowledgeCardUpdateMany: Mock = vi.fn(); 

// Removed separate 'Card' mocks as service uses 'KnowledgeCard'

// ---- GCS Mock Functions ----
export const mockGCSUploadFile: Mock = vi.fn();
export const mockGetSignedUrlForImageGCS: Mock = vi.fn();

// ---- Factory for the Mocked Prisma Client (using vi.fn mocks) ----
export function createMockedPrismaClient(): PrismaClient {
  const baseModelOps = {
    upsert: vi.fn(), 
    count: vi.fn(), 
    aggregate: vi.fn(), 
    groupBy: vi.fn(), 
    findFirstOrThrow: vi.fn(), 
    findUniqueOrThrow: vi.fn(),
  };

  const folderDelegateMethods = {
    findMany: mockFolderFindMany, create: mockFolderCreate, findUnique: mockFolderFindUnique, deleteMany: mockFolderDeleteMany, update: mockFolderUpdate, delete: mockFolderDelete, updateMany: mockFolderUpdateMany,
    ...baseModelOps, findFirst: mockFolderFindUnique, 
  };
  const userDelegateMethods = {
    create: mockUserCreate, deleteMany: mockUserDeleteMany, findUnique: mockUserFindUnique, findMany: vi.fn(), update: vi.fn(), delete: vi.fn(),
    ...baseModelOps, findFirst: mockUserFindUnique,
  };
  const imageRecordDelegateMethods = {
    create: mockImageRecordCreate, findUnique: mockImageRecordFindUnique, update: mockImageRecordUpdate, deleteMany: mockImageRecordDeleteMany, findMany: vi.fn(), delete: vi.fn(),
    ...baseModelOps, findFirst: mockImageRecordFindUnique,
  };
  const knowledgeCardDelegateMethods = {
    findUnique: mockKnowledgeCardFindUnique, 
    findFirst: mockKnowledgeCardFindFirst, 
    findMany: mockKnowledgeCardFindMany, 
    create: mockKnowledgeCardCreate, 
    update: mockKnowledgeCardUpdate, 
    delete: mockKnowledgeCardDelete, 
    deleteMany: mockKnowledgeCardDeleteMany,
    updateMany: mockKnowledgeCardUpdateMany,
    ...baseModelOps,
  };

  // For $transaction, ensure the tx object passed to the callback also has correctly mapped mock functions
  const txClientDefinition = {
    folder: folderDelegateMethods,
    user: userDelegateMethods,
    imageRecord: imageRecordDelegateMethods,
    knowledgeCard: knowledgeCardDelegateMethods,
    // No 'card' property here
  } as any;

  const client = {
    $connect: vi.fn().mockResolvedValue(undefined),
    $disconnect: vi.fn().mockResolvedValue(undefined),
    $on: vi.fn(),
    $use: vi.fn(),
    $executeRaw: vi.fn().mockResolvedValue(0),
    $executeRawUnsafe: vi.fn().mockResolvedValue(0),
    $queryRaw: vi.fn().mockResolvedValue([]),
    $queryRawUnsafe: vi.fn().mockResolvedValue([]),
    $transaction: vi.fn().mockImplementation(async (arg: any) => {
      if (typeof arg === 'function') { 
        try {
            return await arg(txClientDefinition); // Pass the correctly structured tx client
        } catch(e) {
            throw e;
        }
      } 
      return []; 
    }),
    folder: folderDelegateMethods,
    user: userDelegateMethods,
    imageRecord: imageRecordDelegateMethods,
    knowledgeCard: knowledgeCardDelegateMethods, // Corrected: Use knowledgeCardDelegateMethods
    // Ensure no 'card' delegate here
  } as unknown as PrismaClient;

  return client;
}
