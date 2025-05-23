/**
 * @vitest-environment node
 */
// import { PUT, DELETE } from '@/app/api/folders/[folderId]/route'; // Removed: direct handler imports
// import { getCurrentUserId } from '@/lib/sessionUtils'; // Removed: sessionUtils mock
// import { NextRequest } from 'next/server'; // Removed: NextRequest
import request from 'supertest'; // Added: supertest
import { makeTestServer, TestServer } from '../../../../../helpers/testServer'; // Added: testServer, path for future location
import { Prisma } from '@prisma/client'; 
import { vi, Mock, describe, it, expect, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

import {
  MOCK_USER_ID, // Added: MOCK_USER_ID
  mockFolderFindUnique,
  mockFolderUpdate,
  mockFolderDelete,
  mockKnowledgeCardUpdateMany, 
  mockFolderUpdateMany,      
  // mockUserCreate, // Not strictly needed if beforeEach user setup is via global prisma and not this mock
  // mockUserDeleteMany, // Same as above
} from '../../../../../helpers/apiTestSetup'; // Path for future location

// Removed: vi.mock('@/lib/sessionUtils', ...)

let testApp: TestServer; // Added: testApp

beforeAll(async () => { // Added: beforeAll for testApp
  testApp = await makeTestServer();
});

afterAll(async () => { // Added: afterAll for testApp
  if (testApp) {
    await testApp.close();
  }
});

describe('API /api/folders/[folderId]', () => {
  // const mockUserId = 'user-dynamic-123'; // Replaced by MOCK_USER_ID from apiTestSetup
  const mockFolderId = 'clfolderidx123456789'; // Using a more generic CUID-like mock ID
  const trulyInvalidFolderIdFormat = 'bad-id-format';
  const nonExistentValidCuid = 'clnonexist1234567890';

  beforeEach(() => {
    // (getCurrentUserId as Mock).mockReset(); // Removed
    // (getCurrentUserId as Mock).mockResolvedValue(MOCK_USER_ID); // Removed

    mockFolderFindUnique.mockReset();
    mockFolderUpdate.mockReset();
    mockFolderDelete.mockReset();
    mockKnowledgeCardUpdateMany.mockReset();
    mockFolderUpdateMany.mockReset();
    
    // It's assumed that user creation for MOCK_USER_ID is handled globally 
    // or in a shared beforeEach if necessary, like in other refactored tests.
    // If these tests specifically need to ensure the MOCK_USER_ID exists via direct prisma call in beforeEach,
    // that would use (globalThis as any).__PRISMA__.user.create similar to import-by-url test.
    // For now, assuming MOCK_USER_ID is usable for X-Test-User-Id header.
  });

  afterEach(() => { // Added afterEach for vi.restoreAllMocks()
    vi.restoreAllMocks();
  });

  // --- PUT (Rename) Tests ---
  describe('PUT /api/folders/[folderId]', () => {
    const validNewName = 'Updated Folder Name';

    it('should return 400 if folderId is invalid format', async () => {
      const response = await request(testApp.url)
        .put(`/api/folders/${trulyInvalidFolderIdFormat}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify({ name: validNewName }));

      expect(response.status).toBe(400);
      // Zod validation in the route now directly returns error details in the body
      expect(response.body.errors?.folderId).toBeDefined(); 
    });

    it('should return 401 if user is not authenticated', async () => {
      const response = await request(testApp.url)
        .put(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', 'null') // Simulate unauthenticated
        .set('Content-Type', 'application/json')
        .send(JSON.stringify({ name: validNewName }));
      expect(response.status).toBe(401);
    });

    it('should return 400 if name is missing or invalid', async () => {
      mockFolderFindUnique.mockResolvedValue({ id: mockFolderId, userId: MOCK_USER_ID }); // Pre-condition: folder exists

      const response = await request(testApp.url)
        .put(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify({ name: '  ' })); // Invalid name
        
      expect(response.status).toBe(400);
      // Route should return specific validation error for name field based on Zod schema
      expect(response.body.details?.name).toBeDefined(); 
    });

    it('should return 404 if folder is not found or not owned by user', async () => {
      mockFolderFindUnique.mockResolvedValue(null); // Simulate folder not found/not owned

      const response = await request(testApp.url)
        .put(`/api/folders/${nonExistentValidCuid}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify({ name: validNewName }));

      expect(response.status).toBe(404);
      expect(response.body.error).toContain('Folder not found');
      expect(mockFolderFindUnique).toHaveBeenCalledWith({
        where: { id: nonExistentValidCuid, userId: MOCK_USER_ID },
        select: { id: true }, // Select as per route logic for PUT pre-check
      });
    });

    it('should rename the folder successfully', async () => {
      const mockExistingFolder = { id: mockFolderId, userId: MOCK_USER_ID };
      const mockUpdatedFolderData = { ...mockExistingFolder, name: validNewName };
      
      mockFolderFindUnique.mockResolvedValue(mockExistingFolder); 
      mockFolderUpdate.mockResolvedValue(mockUpdatedFolderData);

      const response = await request(testApp.url)
        .put(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify({ name: validNewName }));

      expect(response.status).toBe(200);
      expect(response.body).toEqual(mockUpdatedFolderData);
      expect(mockFolderUpdate).toHaveBeenCalledWith({
        where: { id: mockFolderId }, // userId check is done by findUnique pre-query
        data: { name: validNewName },
      });
    });

    it('should return 409 if new name conflicts with existing folder at same level', async () => {
      const mockExistingFolder = { id: mockFolderId, userId: MOCK_USER_ID };
      mockFolderFindUnique.mockResolvedValue(mockExistingFolder);
      
      const conflictError = new Error('Unique constraint failed');
      (conflictError as any).code = 'P2002'; // Prisma unique constraint violation code
      (conflictError as any).name = 'PrismaClientKnownRequestError'; // Added name property
      (conflictError as any).meta = { target: ['name', 'parentId', 'userId'] }; // Example meta
      mockFolderUpdate.mockRejectedValue(conflictError);

      const response = await request(testApp.url)
        .put(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify({ name: 'Conflicting Name' }));

      expect(response.status).toBe(409);
      expect(response.body.error).toContain('A folder with this name already exists');
    });

    it('should return 500 for other database errors during update', async () => {
      const mockExistingFolder = { id: mockFolderId, userId: MOCK_USER_ID };
      mockFolderFindUnique.mockResolvedValue(mockExistingFolder);
      mockFolderUpdate.mockRejectedValue(new Error('Some other DB error'));

      const response = await request(testApp.url)
        .put(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify({ name: validNewName }));
        
      expect(response.status).toBe(500);
      // Assuming generic error message from route for unhandled errors
      expect(response.body.error).toBe('Internal Server Error'); 
    });
  });

  // --- DELETE Tests ---
  describe('DELETE /api/folders/[folderId]', () => {
    it('should return 400 if folderId is invalid format', async () => {
      const response = await request(testApp.url)
        .delete(`/api/folders/${trulyInvalidFolderIdFormat}`)
        .set('X-Test-User-Id', MOCK_USER_ID);
      expect(response.status).toBe(400);
      expect(response.body.errors?.folderId).toBeDefined();
    });

    it('should return 401 if user is not authenticated', async () => {
      const response = await request(testApp.url)
        .delete(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', 'null');
      expect(response.status).toBe(401);
    });

    it('should return 404 if folder is not found or not owned by user', async () => {
      mockFolderFindUnique.mockResolvedValue(null); // Simulate folder not found/not owned

      const response = await request(testApp.url)
        .delete(`/api/folders/${nonExistentValidCuid}`)
        .set('X-Test-User-Id', MOCK_USER_ID);

      expect(response.status).toBe(404);
      expect(response.body.error).toContain('Folder not found or not owned by user');
      expect(mockFolderFindUnique).toHaveBeenCalledWith({
        where: { id: nonExistentValidCuid, userId: MOCK_USER_ID },
        // Select needs to match what the DELETE handler queries for its pre-check
        select: { parentId: true }, 
      });
    });

    it('should delete the folder successfully if it is empty and owned', async () => {
      const mockFolderData = { id: mockFolderId, userId: MOCK_USER_ID, _count: { cards: 0, children: 0 }, parentId: null };
      mockFolderFindUnique.mockResolvedValue(mockFolderData);
      (mockKnowledgeCardUpdateMany as Mock).mockResolvedValue({ count: 0 }); 
      (mockFolderUpdateMany as Mock).mockResolvedValue({ count: 0 });      
      mockFolderDelete.mockResolvedValue({ id: mockFolderId }); 

      const response = await request(testApp.url)
        .delete(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID);

      expect(response.status).toBe(200);
      expect(response.body.message).toBe('Folder deleted successfully');
      expect(mockFolderDelete).toHaveBeenCalledWith({ where: { id: mockFolderId } });
      // Verify calls for reparenting children/cards (should not happen or be no-op if folder is empty)
      // expect(mockKnowledgeCardUpdateMany).toHaveBeenCalledTimes(0); // This might need to be 1 if always called
      // expect(mockFolderUpdateMany).toHaveBeenCalledTimes(0);      // This might need to be 1 if always called
    });

    // Add test for deleting a non-empty folder (should fail or reparent)
    // Add test for transaction failure during delete (if applicable)

    it('should return 500 for database errors during pre-delete check', async () => {
      mockFolderFindUnique.mockRejectedValue(new Error('Find failed during pre-delete'));
      const response = await request(testApp.url)
        .delete(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID);
      expect(response.status).toBe(500);
      expect(response.body.error).toBe('Internal Server Error');
    });

    it('should return 500 for database errors during actual delete operation', async () => {
      const mockFolderData = { id: mockFolderId, userId: MOCK_USER_ID, _count: { cards: 0, children: 0 }, parentId: null };
      mockFolderFindUnique.mockResolvedValue(mockFolderData);
      (mockKnowledgeCardUpdateMany as Mock).mockResolvedValue({ count: 0 }); 
      (mockFolderUpdateMany as Mock).mockResolvedValue({ count: 0 });   
      mockFolderDelete.mockRejectedValue(new Error('Actual delete failed'));

      const response = await request(testApp.url)
        .delete(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID);
      expect(response.status).toBe(500);
      expect(response.body.error).toBe('Internal Server Error');
    });
  });
}); 