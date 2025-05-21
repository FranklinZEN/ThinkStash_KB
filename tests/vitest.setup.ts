// tests/vitest.setup.ts
import '@testing-library/jest-dom/vitest'; 
import { server } from '../src/mocks/server'; 
import { vi } from 'vitest'; 
import { prismaMock, resetPrismaMock } from './__helpers__/prisma-mock'; 

// Import singleton mock functions from helpers
import { mockGetCardLogic, mockUpdateCardLogic, mockDeleteCardLogic, mockHandleCardImageAssociations } from './__helpers__/card-service-mock';
import { mockGetFoldersLogic, mockCreateFolderLogic } from './__helpers__/folder-service-mock';

// --- Global Prisma Mock ---
vi.mock('@/lib/prisma', () => ({
  __esModule: true,
  default: prismaMock,
  prisma: prismaMock, 
}));

// --- Global Session Utils Mock ---
export const mockGetCurrentUserId = vi.fn(); 
vi.mock('@/lib/sessionUtils', () => ({
  __esModule: true,
  getCurrentUserId: mockGetCurrentUserId,
}));

// --- Global Card Service Mock ---
vi.mock('@/lib/services/cardService', () => ({
  __esModule: true,
  getCardLogic: mockGetCardLogic,
  updateCardLogic: mockUpdateCardLogic,
  deleteCardLogic: mockDeleteCardLogic,
  handleCardImageAssociations: mockHandleCardImageAssociations,
}));

// --- Global Folder Service Mock ---
vi.mock('@/lib/services/folderService', () => ({
  __esModule: true,
  getFoldersLogic: mockGetFoldersLogic,
  createFolderLogic: mockCreateFolderLogic,
}));

// MSW server lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));

afterEach(() => {
  server.resetHandlers();
  resetPrismaMock(); 
});

afterAll(() => server.close()); 