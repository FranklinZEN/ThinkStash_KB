/**
 * @vitest-environment node
 */
import request from 'supertest'; // Added supertest
import { makeTestServer, TestServer } from '@/tests/helpers/testServer'; // USE ALIAS
// import { NextRequest } from 'next/server'; // No longer directly needed for constructing req
import { Prisma } from '@prisma/client'; 
import { vi, Mock } from 'vitest';

import {
  MOCK_USER_ID, // Using shared MOCK_USER_ID
  mockFolderFindUnique,
  mockFolderUpdate,
  mockFolderDelete,
  mockKnowledgeCardUpdateMany,
  mockFolderUpdateMany,
} from '@/tests/helpers/apiTestSetup'; // USE ALIAS

let testServer: TestServer; // Re-add
let currentTestServerUrl: string; // Re-add

beforeAll(async () => { // Re-add
  console.log('[[folderId] test beforeAll] Starting test server...');
  testServer = await makeTestServer();
  currentTestServerUrl = testServer.url;
  console.log(`[[folderId] test beforeAll] Test server started on ${currentTestServerUrl}`);
});

afterAll(async () => { // Re-add
  if (testServer?.close) {
    console.log('[[folderId] test afterAll] Closing test server...');
    await testServer.close();
    console.log('[[folderId] test afterAll] Test server closed.');
  }
});

describe('API /api/folders/[folderId]', () => {
  const mockFolderId = 'cmao1cph90004u5jsmlpf0lku';
  const trulyInvalidFolderIdFormat = 'bad-id-format';
  const nonExistentValidCuid = 'cmao3szy30001u5v84edvgpgj';

  beforeEach(() => {
    mockFolderFindUnique.mockReset();
    mockFolderUpdate.mockReset();
    mockFolderDelete.mockReset();
    mockKnowledgeCardUpdateMany.mockReset();
    mockFolderUpdateMany.mockReset();
  });

  // --- PATCH (Rename) Tests ---
  describe('PATCH /api/folders/[folderId]', () => {
    const validNewName = 'Updated Folder Name';

    it('should return 400 if folderId is invalid format', async () => {
       const response = await request(currentTestServerUrl)
         .patch(`/api/folders/${trulyInvalidFolderIdFormat}`)
         .set('X-Test-User-Id', MOCK_USER_ID)
         .send({ name: validNewName });
       expect(response.status).toBe(400);
       expect(response.body.error).toBe('Invalid folder ID format');
     });

    it('should return 401 if user is not authenticated', async () => {
      const response = await request(currentTestServerUrl)
        .patch(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', 'null') 
        .send({ name: validNewName });
      expect(response.status).toBe(401);
    });

    it('should return 400 if name is missing or invalid', async () => {
      mockFolderFindUnique.mockResolvedValue({ id: mockFolderId, userId: MOCK_USER_ID });
      const response = await request(currentTestServerUrl)
        .patch(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .send({ name: '  ' }); 
      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Validation failed'); 
    });

    it('should return 404 if folder is not found or not owned by user', async () => {
      mockFolderFindUnique.mockResolvedValue(null);
      const response = await request(currentTestServerUrl)
        .patch(`/api/folders/${nonExistentValidCuid}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .send({ name: validNewName });
      expect(response.status).toBe(404);
      expect(response.body.error).toContain('Folder not found or not owned by user');
      expect(mockFolderFindUnique).toHaveBeenCalledWith({
        where: { id: nonExistentValidCuid, userId: MOCK_USER_ID },
      });
    });

    it('should rename the folder successfully', async () => {
      const mockExistingFolder = { id: mockFolderId, userId: MOCK_USER_ID, name: 'Old Name' }; 
      const mockUpdatedFolderData = { ...mockExistingFolder, name: validNewName }; 
      
      mockFolderFindUnique.mockResolvedValue(mockExistingFolder); 
      mockFolderUpdate.mockResolvedValue(mockUpdatedFolderData); 

      const response = await request(currentTestServerUrl)
        .patch(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .send({ name: validNewName });

      expect(response.status).toBe(200);
      expect(response.body).toEqual(mockUpdatedFolderData);
      expect(mockFolderUpdate).toHaveBeenCalledWith({
        where: { id: mockFolderId }, 
        data: { name: validNewName },
        select: expect.any(Object), 
      });
    });

    it('should return 409 if new name conflicts with existing folder at same level', async () => {
      const mockExistingFolder = { id: mockFolderId, userId: MOCK_USER_ID, parentId: 'parent1' }; 
      mockFolderFindUnique.mockResolvedValue(mockExistingFolder);
      const conflictError = new Prisma.PrismaClientKnownRequestError(
        'Unique constraint failed on the fields: (`name`, `parentId`, `userId`)',
        { code: 'P2002', clientVersion: 'test' }
      );
      mockFolderUpdate.mockRejectedValue(conflictError);

      const response = await request(currentTestServerUrl)
        .patch(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .send({ name: 'Conflicting Name' });
      expect(response.status).toBe(409);
      expect(response.body.error).toContain('A folder with this name already exists at this level');
    });

     it('should return 500 for other database errors during update', async () => {
        mockFolderFindUnique.mockResolvedValue({ id: mockFolderId, userId: MOCK_USER_ID });
        const dbError = new Error('Update failed unexpectedly');
        mockFolderUpdate.mockRejectedValue(dbError);
        const response = await request(currentTestServerUrl)
            .patch(`/api/folders/${mockFolderId}`)
            .set('X-Test-User-Id', MOCK_USER_ID)
            .send({ name: validNewName });
        expect(response.status).toBe(500);
        expect(response.body.error).toBe('Failed to update folder');
     });
  });

  // --- DELETE Tests ---
  describe('DELETE /api/folders/[folderId]', () => {
     it('should return 400 if folderId is invalid format', async () => {
       const response = await request(currentTestServerUrl)
        .delete(`/api/folders/${trulyInvalidFolderIdFormat}`)
        .set('X-Test-User-Id', MOCK_USER_ID);
       expect(response.status).toBe(400);
       expect(response.body.error).toBe('Invalid folder ID format');
     });

    it('should return 401 if user is not authenticated', async () => {
      const response = await request(currentTestServerUrl)
        .delete(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', 'null');
      expect(response.status).toBe(401);
    });

    it('should return 404 if folder is not found or not owned by user', async () => {
      mockFolderFindUnique.mockResolvedValue(null);
      const response = await request(currentTestServerUrl)
        .delete(`/api/folders/${nonExistentValidCuid}`)
        .set('X-Test-User-Id', MOCK_USER_ID);
      expect(response.status).toBe(404);
      expect(response.body.error).toContain('Folder not found or not owned by user');
      expect(mockFolderFindUnique).toHaveBeenCalledWith({
        where: { id: nonExistentValidCuid, userId: MOCK_USER_ID },
        select: { parentId: true, _count: { select: { children: true, cards: true } } }, 
      });
    });

    it('should delete the folder successfully if it is empty and owned', async () => {
      const mockFolderData = { id: mockFolderId, userId: MOCK_USER_ID, _count: { cards: 0, children: 0 }, parentId: null };
      mockFolderFindUnique.mockResolvedValue(mockFolderData); 
      mockFolderDelete.mockResolvedValue({ id: mockFolderId }); 
      mockKnowledgeCardUpdateMany.mockResolvedValue({ count: 0 }); 
      mockFolderUpdateMany.mockResolvedValue({ count: 0 });      

      const response = await request(currentTestServerUrl)
        .delete(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID);
        
      expect(response.status).toBe(200);
      expect(response.body.message).toBe('Folder deleted successfully');
      expect(mockFolderDelete).toHaveBeenCalledWith({ where: { id: mockFolderId } });
    });

    it('should return 500 for database errors during delete check', async () => {
      const dbError = new Error('Find for delete failed');
      mockFolderFindUnique.mockRejectedValue(dbError);
      const response = await request(currentTestServerUrl)
        .delete(`/api/folders/${mockFolderId}`)
        .set('X-Test-User-Id', MOCK_USER_ID);
      expect(response.status).toBe(500);
      expect(response.body.error).toBe('Failed to delete folder'); 
    });

     it('should return 500 for database errors during actual delete', async () => {
        const mockFolderData = { id: mockFolderId, userId: MOCK_USER_ID, _count: { cards: 0, children: 0 }, parentId: null };
        mockFolderFindUnique.mockResolvedValue(mockFolderData);
        mockKnowledgeCardUpdateMany.mockResolvedValue({ count: 0 }); 
        mockFolderUpdateMany.mockResolvedValue({ count: 0 });      
        const dbError = new Error('Actual delete failed');
        mockFolderDelete.mockRejectedValue(dbError);

        const response = await request(currentTestServerUrl)
          .delete(`/api/folders/${mockFolderId}`)
          .set('X-Test-User-Id', MOCK_USER_ID);
        expect(response.status).toBe(500);
        expect(response.body.error).toBe('Failed to delete folder');
     });
  });
}); 