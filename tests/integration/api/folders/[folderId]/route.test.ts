/**
 * @vitest-environment node
 */
import { PUT, DELETE } from '@/app/api/folders/[folderId]/route'; // Import handlers
import { getCurrentUserId } from '@/lib/sessionUtils';
import { NextRequest } from 'next/server'; // Import NextRequest
import { Prisma } from '@prisma/client'; // Import Prisma namespace
import { vi, Mock } from 'vitest'; // Import vi and Mock from vitest

// Import the mock functions that are part of the globally injected Prisma client
import {
  mockFolderFindUnique,
  mockFolderUpdate,
  mockFolderDelete,
  mockKnowledgeCardUpdateMany, // For prisma.knowledgeCard.updateMany
  mockFolderUpdateMany,      // For prisma.folder.updateMany
  // Add any other specific mock functions needed by these tests
} from '../../../../helpers/apiTestSetup';

// Remove diagnostic logs
// console.log(`[folders/[folderId]/route.test.ts] Imported prisma ID (after explicit jest.mock): ${(prisma as any).SETUP_FILE_CONFIGURED_ID}`);
// console.log(`[folders/[folderId]/route.test.ts] Does prisma.folder.findUnique have mockResolvedValue? ${!!(prisma.folder.findUnique as any)?.mockResolvedValue}`);
// console.log(`[folders/[folderId]/route.test.ts] Does imported prisma.$transaction have mockImplementation? ${!!(prisma.$transaction as any)?.mockImplementation}`);

vi.mock('@/lib/sessionUtils', () => ({
  getCurrentUserId: vi.fn(),
}));

describe('API /api/folders/[folderId]', () => {
  const mockUserId = 'user-dynamic-123';
  const mockFolderId = 'cmao1cph90004u5jsmlpf0lku';
  const trulyInvalidFolderIdFormat = 'bad-id-format';
  const nonExistentValidCuid = 'cmao3szy30001u5v84edvgpgj';

  beforeEach(() => {
    // vi.clearAllMocks(); // Handled by global setup or mockReset
    // mockReset(actualPrismaMockInstance); // Removed, global mock handles reset
    (getCurrentUserId as Mock).mockReset();
    (getCurrentUserId as Mock).mockResolvedValue(mockUserId);

    // Reset the imported Prisma mock functions
    mockFolderFindUnique.mockReset();
    mockFolderUpdate.mockReset();
    mockFolderDelete.mockReset();
    mockKnowledgeCardUpdateMany.mockReset();
    mockFolderUpdateMany.mockReset();
  });

  // --- PUT (Rename) Tests ---
  describe('PUT', () => {
    const validNewName = 'Updated Folder Name';

    it('should return 400 if folderId is invalid format', async () => {
       const request = new NextRequest(`http://localhost/api/folders/${trulyInvalidFolderIdFormat}`, {
         method: 'PUT',
         body: JSON.stringify({ name: validNewName })
       });
       const response = await PUT(request, { params: { folderId: trulyInvalidFolderIdFormat } }); // No Promise.resolve needed for params
       expect(response.status).toBe(400);
       const body = await response.json();
       expect(body.errors?.folderId).toBeDefined();
     });

    it('should return 401 if user is not authenticated', async () => {
      (getCurrentUserId as Mock).mockResolvedValue(null);
      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: validNewName })
      });
      const response = await PUT(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(401);
    });

    it('should return 400 if name is missing or invalid', async () => {
      const mockExistingFolder = { id: mockFolderId, userId: mockUserId };
      mockFolderFindUnique.mockResolvedValue(mockExistingFolder);

      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: '  ' })
      });
      const response = await PUT(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(400);
      const body = await response.json();
      expect(body.details?.name).toBeDefined(); 
    });

    it('should return 404 if folder is not found or not owned by user', async () => {
      mockFolderFindUnique.mockResolvedValue(null);
      const request = new NextRequest(`http://localhost/api/folders/${nonExistentValidCuid}`, {
        method: 'PUT',
        body: JSON.stringify({ name: validNewName })
      });
      const response = await PUT(request, { params: { folderId: nonExistentValidCuid } });
      expect(response.status).toBe(404);
      const body = await response.json();
      expect(body.error).toContain('Folder not found');
      expect(mockFolderFindUnique).toHaveBeenCalledWith({
        where: { id: nonExistentValidCuid, userId: mockUserId },
        select: { id: true },
      });
    });

    it('should rename the folder successfully', async () => {
      const mockExistingFolder = { id: mockFolderId, userId: mockUserId };
      const mockUpdatedFolder = { ...mockExistingFolder, name: validNewName };
      mockFolderFindUnique.mockResolvedValue(mockExistingFolder); 
      mockFolderUpdate.mockResolvedValue(mockUpdatedFolder);

      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: validNewName })
      });
      const response = await PUT(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(200);
      const body = await response.json();
      expect(body).toEqual(mockUpdatedFolder);
      expect(mockFolderUpdate).toHaveBeenCalledWith({
        where: { id: mockFolderId },
        data: { name: validNewName },
      });
    });

    it('should return 409 if new name conflicts with existing folder at same level', async () => {
      const mockExistingFolder = { id: mockFolderId, userId: mockUserId };
      mockFolderFindUnique.mockResolvedValue(mockExistingFolder);
      const conflictError = new Error('Unique constraint failed');
      (conflictError as any).code = 'P2002';
      (conflictError as any).name = 'PrismaClientKnownRequestError';
      mockFolderUpdate.mockRejectedValue(conflictError);

      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: 'Conflicting Name' })
      });
      const response = await PUT(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(409);
      const body = await response.json();
      expect(body.error).toContain('already exists at this level');
    });

     it('should return 500 for other database errors during update', async () => {
        const mockExistingFolder = { id: mockFolderId, userId: mockUserId };
        mockFolderFindUnique.mockResolvedValue(mockExistingFolder);
        const dbError = new Error('Update failed');
        mockFolderUpdate.mockRejectedValue(dbError);
        const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, {
            method: 'PUT',
            body: JSON.stringify({ name: validNewName })
        });
        const response = await PUT(request, { params: { folderId: mockFolderId } });
        expect(response.status).toBe(500);
        const body = await response.json();
        expect(body.error).toBe('Internal Server Error');
     });
  });

  // --- DELETE Tests ---
  describe('DELETE', () => {
     it('should return 400 if folderId is invalid format', async () => {
       const request = new NextRequest(`http://localhost/api/folders/${trulyInvalidFolderIdFormat}`, { method: 'DELETE' });
       const response = await DELETE(request, { params: { folderId: trulyInvalidFolderIdFormat } });
       expect(response.status).toBe(400);
     });

    it('should return 401 if user is not authenticated', async () => {
      (getCurrentUserId as Mock).mockResolvedValue(null);
      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(401);
    });

    it('should return 404 if folder is not found or not owned by user', async () => {
      mockFolderFindUnique.mockResolvedValue(null);
      const request = new NextRequest(`http://localhost/api/folders/${nonExistentValidCuid}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: { folderId: nonExistentValidCuid } });
      expect(response.status).toBe(404);
      expect(mockFolderFindUnique).toHaveBeenCalledWith({
        where: { id: nonExistentValidCuid, userId: mockUserId },
        select: { parentId: true, _count: { select: { children: true, cards: true } } }, // Adjusted select based on typical delete pre-checks
      });
    });

    it('should delete the folder successfully if it is empty and owned', async () => {
      const mockFolderData = { id: mockFolderId, userId: mockUserId, _count: { cards: 0, children: 0 }, parentId: null };
      mockFolderFindUnique.mockResolvedValue(mockFolderData);
      mockKnowledgeCardUpdateMany.mockResolvedValue({ count: 0 }); 
      mockFolderUpdateMany.mockResolvedValue({ count: 0 });      
      mockFolderDelete.mockResolvedValue({ id: mockFolderId }); 

      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(200);
      const body = await response.json();
      expect(body.message).toBe('Folder deleted successfully');
      expect(mockFolderDelete).toHaveBeenCalledWith({ where: { id: mockFolderId } });
    });

    it('should return 500 for database errors during delete check', async () => {
      const dbError = new Error('Find failed');
      mockFolderFindUnique.mockRejectedValue(dbError);
      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(500);
    });

     it('should return 500 for database errors during actual delete', async () => {
        const mockFolderData = { id: mockFolderId, userId: mockUserId, _count: { cards: 0, children: 0 }, parentId: null };
        mockFolderFindUnique.mockResolvedValue(mockFolderData);
        mockKnowledgeCardUpdateMany.mockResolvedValue({ count: 0 }); 
        mockFolderUpdateMany.mockResolvedValue({ count: 0 });      
        const dbError = new Error('Delete failed');
        mockFolderDelete.mockRejectedValue(dbError);

        const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
        const response = await DELETE(request, { params: { folderId: mockFolderId } });
        expect(response.status).toBe(500);
     });

  });
}); 