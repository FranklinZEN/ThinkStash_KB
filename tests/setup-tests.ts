import { prismaMock } from './__helpers__/prisma-mock';
import { 
  mockGetCardLogic, 
  mockUpdateCardLogic, 
  mockDeleteCardLogic,
  mockHandleCardImageAssociations // Import new mock
} from './__helpers__/card-service-mock'; // Import service mocks
import {
  mockGetFoldersLogic,
  mockCreateFolderLogic
} from './__helpers__/folder-service-mock'; // Import folder service mocks
import { jest } from '@jest/globals'; // Ensure jest is available for jest.fn()

// This line is critical. It tells Jest to replace the actual module
// with our mock *before* any application code imports it.
// The path '@/lib/prisma' must exactly match how it's imported in your app code.
jest.mock('@/lib/prisma', () => ({
  __esModule: true, // Important for ES Module interop
  default: prismaMock, // SWC/Next.js often looks for `default` export
  prisma: prismaMock,  // If some parts of your code might do `import { prisma } from '@/lib/prisma'`
})); 

// --- Session Utils Mock Setup ---
// Export the mock function instance so tests can control it and assert on it.
export const mockGetCurrentUserId = jest.fn();

jest.mock('@/lib/sessionUtils', () => ({
  __esModule: true,
  getCurrentUserId: mockGetCurrentUserId,
})); 

// --- Card Service Mock Setup (Restored and using singletons) ---
jest.mock('@/lib/services/cardService', () => ({
  __esModule: true,
  getCardLogic: mockGetCardLogic,         // Use imported singleton mock
  updateCardLogic: mockUpdateCardLogic,   // Use imported singleton mock
  deleteCardLogic: mockDeleteCardLogic,   // Use imported singleton mock
  handleCardImageAssociations: mockHandleCardImageAssociations, // Add to mock factory
  // IMPORTANT: Also mock any other named exports from the actual cardService.ts
  // if they are imported anywhere, even if not directly by this API route,
  // to prevent them from being undefined. For types like UpdateCardData, it's usually fine
  // as they are type-only imports or just re-exported if the mock doesn't provide them.
  // If UpdateCardData or other specific named exports are causing issues by being undefined
  // when the actual cardService is mocked, provide dummy versions here if necessary.
  // For now, assuming only the logic functions are crucial for the mock's behavior.
})); 

// --- Folder Service Mock Setup ---
jest.mock('@/lib/services/folderService', () => ({
  __esModule: true,
  getFoldersLogic: mockGetFoldersLogic,
  createFolderLogic: mockCreateFolderLogic,
})); 