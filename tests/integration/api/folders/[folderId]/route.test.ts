import { PUT, DELETE } from '@/app/api/folders/[folderId]/route'; // Import handlers
import { getCurrentUserId } from '@/lib/sessionUtils';
import { NextRequest } from 'next/server'; // Import NextRequest
import { Prisma } from '@prisma/client'; // Import Prisma namespace

// Explicitly mock prisma again to ensure this file gets the deep mock where all methods are jest.fn()
jest.mock('@/lib/prisma'); 

import prisma from '@/lib/prisma'; 

// Remove diagnostic logs
// console.log(`[folders/[folderId]/route.test.ts] Imported prisma ID (after explicit jest.mock): ${(prisma as any).SETUP_FILE_CONFIGURED_ID}`);
// console.log(`[folders/[folderId]/route.test.ts] Does prisma.folder.findUnique have mockResolvedValue? ${!!(prisma.folder.findUnique as any)?.mockResolvedValue}`);
// console.log(`[folders/[folderId]/route.test.ts] Does imported prisma.$transaction have mockImplementation? ${!!(prisma.$transaction as any)?.mockImplementation}`);

jest.mock('@/lib/sessionUtils', () => ({
  getCurrentUserId: jest.fn(),
}));

describe('API /api/folders/[folderId]', () => {
  const mockUserId = 'user-dynamic-123';
  const mockFolderId = 'cmao1cph90004u5jsmlpf0lku';
  const trulyInvalidFolderIdFormat = 'bad-id-format';
  const nonExistentValidCuid = 'cmao3szy30001u5v84edvgpgj';

  beforeEach(() => {
    // jest.clearAllMocks(); // Handled by global setup or mockReset
    // mockReset(actualPrismaMockInstance); // Removed, global mock handles reset
    (getCurrentUserId as jest.Mock).mockReset();
    (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
  });

  // --- PUT (Rename) Tests ---
  describe('PUT', () => {
    const validNewName = 'Updated Folder Name';

    it('should return 400 if folderId is invalid format', async () => {
       const request = new NextRequest(`http://localhost/api/folders/${trulyInvalidFolderIdFormat}`, {
         method: 'PUT',
         body: JSON.stringify({ name: validNewName })
       });
       const response = await PUT(request, { params: Promise.resolve({ folderId: trulyInvalidFolderIdFormat }) });
       expect(response.status).toBe(400);
       const body = await response.json();
       expect(body.errors?.folderId).toBeDefined();
     });

    it('should return 401 if user is not authenticated', async () => {
      (getCurrentUserId as jest.Mock).mockResolvedValue(null);
      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: validNewName })
      });
      const response = await PUT(request, { params: Promise.resolve({ folderId: mockFolderId }) });
      expect(response.status).toBe(401);
    });

    it('should return 400 if name is missing or invalid', async () => {
      // Ensure the folder is found for this test, so name validation is hit
      const mockExistingFolder = { id: mockFolderId, userId: mockUserId };
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockExistingFolder);

      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: '  ' })
      });
      const response = await PUT(request, { params: Promise.resolve({ folderId: mockFolderId }) });
      expect(response.status).toBe(400);
      const body = await response.json();
      expect(body.details?.name).toBeDefined(); // Updated to check body.details
    });

    it('should return 404 if folder is not found or not owned by user', async () => {
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(null);
      const request = new NextRequest(`http://localhost/api/folders/${nonExistentValidCuid}`, {
        method: 'PUT',
        body: JSON.stringify({ name: validNewName })
      });
      const response = await PUT(request, { params: Promise.resolve({ folderId: nonExistentValidCuid }) });
      expect(response.status).toBe(404);
      const body = await response.json();
      expect(body.error).toContain('Folder not found');
      expect(prisma.folder.findUnique).toHaveBeenCalledWith({
        where: { id: nonExistentValidCuid, userId: mockUserId },
        select: { id: true },
      });
    });

    it('should rename the folder successfully', async () => {
      const mockExistingFolder = { id: mockFolderId, userId: mockUserId };
      const mockUpdatedFolder = { ...mockExistingFolder, name: validNewName };
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockExistingFolder); // Ownership check passes
      (prisma.folder.update as jest.Mock).mockResolvedValue(mockUpdatedFolder);

      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: validNewName })
      });
      const response = await PUT(request, { params: Promise.resolve({ folderId: mockFolderId }) });
      expect(response.status).toBe(200);
      const body = await response.json();
      expect(body).toEqual(mockUpdatedFolder);
      expect(prisma.folder.update).toHaveBeenCalledWith({
        where: { id: mockFolderId },
        data: { name: validNewName },
      });
    });

    it('should return 409 if new name conflicts with existing folder at same level', async () => {
      const mockExistingFolder = { id: mockFolderId, userId: mockUserId };
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockExistingFolder);
      const conflictError = new Prisma.PrismaClientKnownRequestError(
        'Unique constraint failed', 
        { code: 'P2002', clientVersion: 'test' }
      );
      (prisma.folder.update as jest.Mock).mockRejectedValue(conflictError);

      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: 'Conflicting Name' })
      });
      const response = await PUT(request, { params: Promise.resolve({ folderId: mockFolderId }) });
      expect(response.status).toBe(409);
      const body = await response.json();
      expect(body.error).toContain('already exists at this level');
    });

     it('should return 500 for other database errors during update', async () => {
        const mockExistingFolder = { id: mockFolderId, userId: mockUserId };
        (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockExistingFolder);
        const dbError = new Error('Update failed');
        (prisma.folder.update as jest.Mock).mockRejectedValue(dbError);
        const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, {
            method: 'PUT',
            body: JSON.stringify({ name: validNewName })
        });
        const response = await PUT(request, { params: Promise.resolve({ folderId: mockFolderId }) });
        expect(response.status).toBe(500);
        const body = await response.json();
        expect(body.error).toBe('Internal Server Error');
     });
  });

  // --- DELETE Tests ---
  describe('DELETE', () => {
     it('should return 400 if folderId is invalid format', async () => {
       const request = new NextRequest(`http://localhost/api/folders/${trulyInvalidFolderIdFormat}`, { method: 'DELETE' });
       const response = await DELETE(request, { params: Promise.resolve({ folderId: trulyInvalidFolderIdFormat }) });
       expect(response.status).toBe(400);
     });

    it('should return 401 if user is not authenticated', async () => {
      (getCurrentUserId as jest.Mock).mockResolvedValue(null);
      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: Promise.resolve({ folderId: mockFolderId }) });
      expect(response.status).toBe(401);
    });

    it('should return 404 if folder is not found or not owned by user', async () => {
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(null);
      const request = new NextRequest(`http://localhost/api/folders/${nonExistentValidCuid}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: Promise.resolve({ folderId: nonExistentValidCuid }) });
      expect(response.status).toBe(404);
      expect(prisma.folder.findUnique).toHaveBeenCalledWith({
        where: { id: nonExistentValidCuid, userId: mockUserId },
        select: { parentId: true },
      });
    });

    it('should delete the folder successfully if it is empty and owned', async () => {
      const mockFolder = { id: mockFolderId, userId: mockUserId, _count: { cards: 0, children: 0 }, parentId: null };
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockFolder);
      (prisma.knowledgeCard.updateMany as jest.Mock).mockResolvedValue({ count: 0 });
      (prisma.folder.updateMany as jest.Mock).mockResolvedValue({ count: 0 });
      
      const specificDeleteMock = jest.fn().mockResolvedValue({ id: mockFolderId });
      (prisma.folder.delete as jest.Mock) = specificDeleteMock; // Assign our own jest.fn()

      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: Promise.resolve({ folderId: mockFolderId }) });
      expect(response.status).toBe(200);
      const body = await response.json();
      expect(body.message).toBe('Folder deleted successfully');
      expect(specificDeleteMock).toHaveBeenCalledWith({ where: { id: mockFolderId } }); // Assert on our specific mock
    });

    it('should return 500 for database errors during delete check', async () => {
      const dbError = new Error('Find failed');
      (prisma.folder.findUnique as jest.Mock).mockRejectedValue(dbError);
      const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: Promise.resolve({ folderId: mockFolderId }) });
      expect(response.status).toBe(500);
    });

     it('should return 500 for database errors during actual delete', async () => {
        const mockFolder = { id: mockFolderId, userId: mockUserId, _count: { cards: 0, children: 0 }, parentId: null };
        (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockFolder);
        (prisma.knowledgeCard.updateMany as jest.Mock).mockResolvedValue({ count: 0 });
        (prisma.folder.updateMany as jest.Mock).mockResolvedValue({ count: 0 });
        const dbError = new Error('Delete failed');
        
        const specificDeleteMockWithError = jest.fn().mockRejectedValue(dbError);
        (prisma.folder.delete as jest.Mock) = specificDeleteMockWithError; // Assign our own jest.fn()

        const request = new NextRequest(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
        const response = await DELETE(request, { params: Promise.resolve({ folderId: mockFolderId }) });
        expect(response.status).toBe(500);
     });

  });
}); 