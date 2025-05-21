/**
 * @jest-environment node
 */
import 'next-test-api-route-handler'; // Must be first
import { testApiHandler } from 'next-test-api-route-handler';
// import * as folderApiHandler from '@/app/api/folders/route'; // Will be required in beforeEach
import { prismaMock } from 'tests/__helpers__/prisma-mock'; 
import { mockGetCurrentUserId } from 'tests/setup-tests'; 
// Import singleton mock functions for folderService
import { 
  mockGetFoldersLogic,
  mockCreateFolderLogic
} from 'tests/__helpers__/folder-service-mock'; 
import { jest } from '@jest/globals'; // For jest.resetAllMocks()

// No local jest.mock for services or sessionUtils here

const MOCK_USER_ID_FOLDERS = 'user-folders-test-123'; // Different user ID for clarity if needed

const createFolderPayload = (name: string, parentId?: string | null) => ({ name, parentId });

let folderApiHandler: any; // To be set in beforeEach

describe('Folder API Routes /api/folders', () => {
  beforeEach(() => {
    jest.resetAllMocks();
    // Default to an authenticated user for most tests
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID_FOLDERS);
    // prismaMock is reset by its own beforeEach in tests/__helpers__/prisma-mock.ts
    // Require the module here, after mocks are reset and configured for the test run
    folderApiHandler = require('@/app/api/folders/route');
  });

  describe('GET /api/folders', () => {
    it('should return 401 if user is not authenticated', async () => {
      mockGetCurrentUserId.mockReset().mockResolvedValue(null); // Override for this test
      await testApiHandler({
        appHandler: folderApiHandler,
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'GET' });
          const json = await res.json();
          expect(res.status).toBe(401);
          expect(json.error).toBe('Unauthorized');
          expect(mockGetFoldersLogic).not.toHaveBeenCalled();
        },
      });
    });

    it('should call getFoldersLogic and return its success response', async () => {
      // mockGetCurrentUserId is already MOCK_USER_ID_FOLDERS from outer beforeEach
      const serviceResponseData = [{ id: 'f1', name: 'Folder1', parentId: null, updatedAt: new Date(), _count: { cards: 0 } }];
      const serviceResult = { success: true, data: serviceResponseData, status: 200 };
      mockGetFoldersLogic.mockResolvedValue(serviceResult);

      await testApiHandler({
        appHandler: folderApiHandler,
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'GET' });
          const json = await res.json();
          expect(mockGetFoldersLogic).toHaveBeenCalledWith(MOCK_USER_ID_FOLDERS, prismaMock);
          expect(res.status).toBe(200);
          expect(json).toEqual(serviceResponseData.map(f => ({...f, updatedAt: f.updatedAt.toISOString() })));
        },
      });
    });

    it('should call getFoldersLogic and return its error response', async () => {
      const serviceResult = { success: false, error: 'Service layer GET error', status: 500 };
      mockGetFoldersLogic.mockResolvedValue(serviceResult);

      await testApiHandler({
        appHandler: folderApiHandler,
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'GET' });
          const json = await res.json();
          expect(mockGetFoldersLogic).toHaveBeenCalledWith(MOCK_USER_ID_FOLDERS, prismaMock);
          expect(res.status).toBe(500);
          expect(json.error).toBe('Service layer GET error');
        },
      });
    });
  });

  describe('POST /api/folders', () => {
    it('should return 401 if user is not authenticated', async () => {
      mockGetCurrentUserId.mockReset().mockResolvedValue(null);
      await testApiHandler({
        appHandler: folderApiHandler,
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'POST', body: JSON.stringify(createFolderPayload('test')) });
          const json = await res.json();
          expect(res.status).toBe(401);
          expect(json.error).toBe('Unauthorized');
          expect(mockCreateFolderLogic).not.toHaveBeenCalled();
        },
      });
    });

    it('should return 400 for invalid request body (Zod validation fail)', async () => {
      await testApiHandler({
        appHandler: folderApiHandler,
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'POST', body: JSON.stringify({ name: '' }) }); // Empty name
          const json = await res.json();
          expect(res.status).toBe(400);
          expect(json.error).toBe('Validation failed');
          expect(json.details?.name).toBeDefined();
          expect(mockCreateFolderLogic).not.toHaveBeenCalled();
        },
      });
    });

     it('should return 400 for non-JSON request body', async () => {
      await testApiHandler({
        appHandler: folderApiHandler,
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'POST', body: 'not-json' });
          const json = await res.json();
          expect(res.status).toBe(400);
          expect(json.error).toBe('Invalid request body');
          expect(mockCreateFolderLogic).not.toHaveBeenCalled();
        },
      });
    });

    it('should call createFolderLogic and return its success response', async () => {
      const folderName = 'New Folder';
      const parentId = null;
      const payload = { name: folderName, parentId }; // service expects {userId, name, parentId}
      const serviceInput = { userId: MOCK_USER_ID_FOLDERS, name: folderName, parentId };

      const serviceResponseData = { id: 'new-id', name: folderName, parentId, userId: MOCK_USER_ID_FOLDERS };
      const serviceResult = { success: true, data: serviceResponseData, status: 201 };
      mockCreateFolderLogic.mockResolvedValue(serviceResult);

      await testApiHandler({
        appHandler: folderApiHandler,
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'POST', body: JSON.stringify(payload) });
          const json = await res.json();
          expect(mockCreateFolderLogic).toHaveBeenCalledWith(serviceInput, prismaMock);
          expect(res.status).toBe(201);
          expect(json).toEqual(serviceResponseData);
        },
      });
    });

    it('should call createFolderLogic and return its error response', async () => {
      const folderName = 'Existing Folder';
      const payload = createFolderPayload(folderName);
      const serviceInput = { userId: MOCK_USER_ID_FOLDERS, name: folderName, parentId: undefined };
      const serviceResult = { success: false, error: 'Folder exists', status: 409 };
      mockCreateFolderLogic.mockResolvedValue(serviceResult);

      await testApiHandler({
        appHandler: folderApiHandler,
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'POST', body: JSON.stringify(payload) });
          const json = await res.json();
          expect(mockCreateFolderLogic).toHaveBeenCalledWith(serviceInput, prismaMock);
          expect(res.status).toBe(409);
          expect(json.error).toBe(serviceResult.error);
        },
      });
    });
  });
}); 