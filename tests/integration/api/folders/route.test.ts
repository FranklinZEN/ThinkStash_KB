import { GET, POST } from '@/app/api/folders/route'; // Import handlers directly
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createMocks, RequestMethod } from 'node-mocks-http';
import { NextRequest } from 'next/server';
import { mockGetFoldersLogic, mockCreateFolderLogic } from 'tests/__helpers__/folder-service-mock';
import { mockGetCurrentUserId } from 'tests/vitest.setup'; // Import from global VITEST setup
import { prismaMock } from 'tests/__helpers__/prisma-mock';

const API_URL = process.env.TEST_API_URL || 'http://localhost:3000';
const MOCK_USER_ID_FOLDERS = 'user-folders-test-123';

const createFolderPayload = (name: string, parentId?: string | null) => ({ name, parentId });

// Helper to create a mock NextRequest
function mockRequest(method: RequestMethod, body?: any, searchParams?: Record<string, string>) {
  const { req } = createMocks({
    method,
    body: body ? JSON.stringify(body) : undefined,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    url: `/api/folders${searchParams ? '?' + new URLSearchParams(searchParams).toString() : ''}`,
  });
  // node-mocks-http req needs to be adapted to NextRequest-like object
  // A simple way for now, focusing on body parsing and searchParams
  const nextReq = req as unknown as NextRequest & { json: () => Promise<any>, searchParams: URLSearchParams };
  nextReq.json = async () => body ? JSON.parse(JSON.stringify(body)) : Promise.resolve(undefined);
  nextReq.searchParams = new URLSearchParams(searchParams);
  // nextUrl needs to be mocked more completely if the handler uses more parts of it.
  (nextReq as any).nextUrl = { searchParams: new URLSearchParams(searchParams) };
  return nextReq;
}

describe('Folder API Route Handlers /api/folders', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID_FOLDERS);
    // prismaMock reset is handled by its own beforeEach in tests/__helpers__/prisma-mock.ts (now in vitest.setup.ts)
  });

  describe('GET handler', () => {
    it('should return 401 if user is not authenticated', async () => {
      mockGetCurrentUserId.mockReset().mockResolvedValue(null);
      const req = mockRequest('GET');
      const response = await GET(req);
      const json = await response.json();
      expect(response.status).toBe(401);
      expect(json.error).toBe('Unauthorized');
      expect(mockGetFoldersLogic).not.toHaveBeenCalled();
    });

    it('should call getFoldersLogic and return its success response', async () => {
      const serviceResponseData = [{ id: 'f1', name: 'Folder1', parentId: null, updatedAt: new Date(), _count: { cards: 0 } }];
      const serviceResult = { success: true, data: serviceResponseData, status: 200 };
      mockGetFoldersLogic.mockResolvedValue(serviceResult);
      const req = mockRequest('GET');
      const response = await GET(req);
      const json = await response.json();
      expect(mockGetFoldersLogic).toHaveBeenCalledWith(MOCK_USER_ID_FOLDERS, prismaMock);
      expect(response.status).toBe(200);
      expect(json).toEqual(serviceResponseData.map(f => ({...f, updatedAt: f.updatedAt.toISOString() })));
    });

    it('should call getFoldersLogic and return its error response', async () => {
      const serviceResult = { success: false, error: 'Service layer GET error', status: 500 };
      mockGetFoldersLogic.mockResolvedValue(serviceResult);
      const req = mockRequest('GET');
      const response = await GET(req);
      const json = await response.json();
      expect(mockGetFoldersLogic).toHaveBeenCalledWith(MOCK_USER_ID_FOLDERS, prismaMock);
      expect(response.status).toBe(500);
      expect(json.error).toBe('Service layer GET error');
    });
  });

  describe('POST handler', () => {
    it('should return 401 if user is not authenticated', async () => {
      mockGetCurrentUserId.mockReset().mockResolvedValue(null);
      const req = mockRequest('POST', createFolderPayload('test'));
      const response = await POST(req);
      const json = await response.json();
      expect(response.status).toBe(401);
      expect(json.error).toBe('Unauthorized');
      expect(mockCreateFolderLogic).not.toHaveBeenCalled();
    });

    it('should return 400 for invalid request body (Zod validation fail)', async () => {
      const req = mockRequest('POST', { name: '' }); // Empty name
      const response = await POST(req);
      const json = await response.json(); 
      expect(response.status).toBe(400);
      expect(json.error).toBe('Validation failed');
      expect(json.details?.name).toBeDefined(); 
      expect(mockCreateFolderLogic).not.toHaveBeenCalled();
    });

    it('should call createFolderLogic and return its success response', async () => {
      const folderName = 'New Folder';
      const parentId = null;
      const payload = { name: folderName, parentId };
      const serviceInput = { userId: MOCK_USER_ID_FOLDERS, name: folderName, parentId };
      const serviceResponseData = { id: 'new-id', name: folderName, parentId, userId: MOCK_USER_ID_FOLDERS };
      const serviceResult = { success: true, data: serviceResponseData, status: 201 };
      mockCreateFolderLogic.mockResolvedValue(serviceResult);

      const req = mockRequest('POST', payload);
      const response = await POST(req);
      const json = await response.json();

      expect(mockCreateFolderLogic).toHaveBeenCalledWith(serviceInput, prismaMock);
      expect(response.status).toBe(201);
      expect(json).toEqual(serviceResponseData);
    });

    it('should call createFolderLogic and return its error response', async () => {
      const folderName = 'Existing Folder';
      const payload = createFolderPayload(folderName);
      const serviceInput = { userId: MOCK_USER_ID_FOLDERS, name: folderName, parentId: undefined };
      const serviceResult = { success: false, error: 'Folder exists', status: 409 };
      mockCreateFolderLogic.mockResolvedValue(serviceResult);

      const req = mockRequest('POST', payload);
      const response = await POST(req);
      const json = await response.json();

      expect(mockCreateFolderLogic).toHaveBeenCalledWith(serviceInput, prismaMock);
      expect(response.status).toBe(409);
      expect(json.error).toBe(serviceResult.error);
    });
  });
});