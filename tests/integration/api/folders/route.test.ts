/**
 * @jest-environment node
 */
import 'next-test-api-route-handler'; // Must be first
import { testApiHandler } from 'next-test-api-route-handler';
import * as folderApiHandler from '@/app/api/folders/route';
import { getCurrentUserId } from '@/lib/sessionUtils';
import { getFoldersLogic, createFolderLogic } from '@/lib/services/folderService';
// No direct import of prisma here

// Mock dependencies
jest.mock('@/lib/sessionUtils', () => ({
  getCurrentUserId: jest.fn(),
}));
jest.mock('@/lib/services/folderService', () => ({
  getFoldersLogic: jest.fn(),
  createFolderLogic: jest.fn(),
}));

const mockGetCurrentUserId = getCurrentUserId as jest.Mock;
const mockGetFoldersLogic = getFoldersLogic as jest.Mock;
const mockCreateFolderLogic = createFolderLogic as jest.Mock;

const createFolderPayload = (name: string, parentId?: string | null) => ({ name, parentId });

describe('GET /api/folders (Route Handler Tests)', () => {
  beforeEach(() => {
    mockGetCurrentUserId.mockReset();
    mockGetFoldersLogic.mockReset();
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetCurrentUserId.mockResolvedValue(null);
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
    const userId = 'user-123';
    mockGetCurrentUserId.mockResolvedValue(userId);
    // Define what the service mock should return
    const serviceResponseData = [{ id: 'f1', name: 'Folder1', parentId: null, updatedAt: new Date(), _count: { cards: 0 } }];
    const serviceResult = { success: true, data: serviceResponseData, status: 200 };
    mockGetFoldersLogic.mockResolvedValue(serviceResult);

    await testApiHandler({
      appHandler: folderApiHandler,
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        const json = await res.json();
        expect(mockGetFoldersLogic).toHaveBeenCalledWith(userId, expect.anything()); // Prisma is passed by route to service
        expect(res.status).toBe(200);
        // API route returns result.data directly on success for GET
        expect(json).toEqual(serviceResponseData.map(f => ({...f, updatedAt: f.updatedAt.toISOString() })));
      },
    });
  });

  it('should call getFoldersLogic and return its error response', async () => {
    const userId = 'user-123';
    mockGetCurrentUserId.mockResolvedValue(userId);
    const serviceResult = { success: false, error: 'Service layer GET error', status: 500 };
    mockGetFoldersLogic.mockResolvedValue(serviceResult);

    await testApiHandler({
      appHandler: folderApiHandler,
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        const json = await res.json();
        expect(mockGetFoldersLogic).toHaveBeenCalledWith(userId, expect.anything());
        expect(res.status).toBe(500);
        expect(json.error).toBe('Service layer GET error');
      },
    });
  });
});

describe('POST /api/folders (Route Handler Tests)', () => {
  beforeEach(() => {
    mockGetCurrentUserId.mockReset();
    mockCreateFolderLogic.mockReset();
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetCurrentUserId.mockResolvedValue(null);
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
    const userId = 'user-123';
    mockGetCurrentUserId.mockResolvedValue(userId);
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
    const userId = 'user-123';
    mockGetCurrentUserId.mockResolvedValue(userId);
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
    const userId = 'user-123';
    const folderName = 'New Folder';
    const parentId = null;
    const payload = createFolderPayload(folderName, parentId);
    mockGetCurrentUserId.mockResolvedValue(userId);
    const serviceResponseData = { id: 'new-id', name: folderName, parentId, userId };
    const serviceResult = { success: true, data: serviceResponseData, status: 201 };
    mockCreateFolderLogic.mockResolvedValue(serviceResult);

    await testApiHandler({
      appHandler: folderApiHandler,
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'POST', body: JSON.stringify(payload) });
        const json = await res.json();
        expect(mockCreateFolderLogic).toHaveBeenCalledWith(
          { userId, name: folderName, parentId },
          expect.anything()
        );
        expect(res.status).toBe(201);
        expect(json).toEqual(serviceResponseData);
      },
    });
  });

  it('should call createFolderLogic and return its error response', async () => {
    const userId = 'user-123';
    const folderName = 'Existing Folder';
    const payload = createFolderPayload(folderName);
    mockGetCurrentUserId.mockResolvedValue(userId);
    const serviceResult = { success: false, error: 'Folder exists', status: 409 };
    mockCreateFolderLogic.mockResolvedValue(serviceResult);

    await testApiHandler({
      appHandler: folderApiHandler,
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'POST', body: JSON.stringify(payload) });
        const json = await res.json();
        expect(mockCreateFolderLogic).toHaveBeenCalledTimes(1);
        expect(res.status).toBe(409);
        expect(json.error).toBe(serviceResult.error);
      },
    });
  });
}); 