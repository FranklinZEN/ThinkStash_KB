import { PUT, DELETE } from '@/app/api/folders/[folderId]/route'; // Import handlers
import { prisma } from '@/lib/prisma';
import { getCurrentUserId } from '@/lib/sessionUtils';
import { NextResponse } from 'next/server';
import { Prisma } from '@prisma/client';

// Mock dependencies
jest.mock('@/lib/prisma', () => ({
  prisma: {
    folder: {
      findUnique: jest.fn(),
      update: jest.fn(),
      delete: jest.fn(),
    },
  },
}));

jest.mock('@/lib/sessionUtils', () => ({
  getCurrentUserId: jest.fn(),
}));

describe('API /api/folders/[folderId]', () => {
  const mockUserId = 'user-dynamic-123';
  const mockFolderId = 'folder-cuid-123';
  const invalidFolderId = 'invalid-id';

  beforeEach(() => {
    jest.clearAllMocks();
    (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId); // Assume logged in for most tests
  });

  // --- PUT (Rename) Tests ---
  describe('PUT', () => {
    const validNewName = 'Updated Folder Name';

    it('should return 400 if folderId is invalid format', async () => {
       const request = new Request(`http://localhost/api/folders/${invalidFolderId}`, {
         method: 'PUT',
         body: JSON.stringify({ name: validNewName })
       });
       const response = await PUT(request, { params: { folderId: invalidFolderId } });
       expect(response.status).toBe(400);
       const body = await response.json();
       expect(body.errors?.folderId).toBeDefined();
     });

    it('should return 401 if user is not authenticated', async () => {
      (getCurrentUserId as jest.Mock).mockResolvedValue(null);
      const request = new Request(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: validNewName })
      });
      const response = await PUT(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(401);
    });

    it('should return 400 if name is missing or invalid', async () => {
      const request = new Request(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: '  ' })
      });
      const response = await PUT(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(400);
      const body = await response.json();
      expect(body.errors?.name).toBeDefined();
    });

    it('should return 404 if folder is not found or not owned by user', async () => {
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(null);
      const request = new Request(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: validNewName })
      });
      const response = await PUT(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(404);
      const body = await response.json();
      expect(body.error).toContain('Folder not found');
      expect(prisma.folder.findUnique).toHaveBeenCalledWith({
        where: { id: mockFolderId, userId: mockUserId },
        select: { id: true },
      });
    });

    it('should rename the folder successfully', async () => {
      const mockExistingFolder = { id: mockFolderId, userId: mockUserId };
      const mockUpdatedFolder = { ...mockExistingFolder, name: validNewName };
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockExistingFolder); // Ownership check passes
      (prisma.folder.update as jest.Mock).mockResolvedValue(mockUpdatedFolder);

      const request = new Request(`http://localhost/api/folders/${mockFolderId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: validNewName })
      });
      const response = await PUT(request, { params: { folderId: mockFolderId } });
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

      const request = new Request(`http://localhost/api/folders/${mockFolderId}`, {
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
        (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockExistingFolder);
        const dbError = new Error('Update failed');
        (prisma.folder.update as jest.Mock).mockRejectedValue(dbError);
        const request = new Request(`http://localhost/api/folders/${mockFolderId}`, {
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
       const request = new Request(`http://localhost/api/folders/${invalidFolderId}`, { method: 'DELETE' });
       const response = await DELETE(request, { params: { folderId: invalidFolderId } });
       expect(response.status).toBe(400);
     });

    it('should return 401 if user is not authenticated', async () => {
      (getCurrentUserId as jest.Mock).mockResolvedValue(null);
      const request = new Request(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(401);
    });

    it('should return 404 if folder is not found or not owned by user', async () => {
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(null);
      const request = new Request(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(404);
      expect(prisma.folder.findUnique).toHaveBeenCalledWith({
        where: { id: mockFolderId, userId: mockUserId },
        include: { _count: { select: { cards: true, children: true } } },
      });
    });

    it('should return 400 if folder is not empty (contains cards)', async () => {
      const mockFolder = { id: mockFolderId, userId: mockUserId, _count: { cards: 1, children: 0 } };
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockFolder);
      const request = new Request(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(400);
      const body = await response.json();
      expect(body.error).toContain('Folder is not empty');
      expect(prisma.folder.delete).not.toHaveBeenCalled();
    });

     it('should return 400 if folder is not empty (contains sub-folders)', async () => {
       const mockFolder = { id: mockFolderId, userId: mockUserId, _count: { cards: 0, children: 1 } };
       (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockFolder);
       const request = new Request(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
       const response = await DELETE(request, { params: { folderId: mockFolderId } });
       expect(response.status).toBe(400);
       const body = await response.json();
       expect(body.error).toContain('Folder is not empty');
       expect(prisma.folder.delete).not.toHaveBeenCalled();
     });

    it('should delete the folder successfully if it is empty and owned', async () => {
      const mockFolder = { id: mockFolderId, userId: mockUserId, _count: { cards: 0, children: 0 } };
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockFolder);
      (prisma.folder.delete as jest.Mock).mockResolvedValue({ id: mockFolderId }); // Simulate successful delete

      const request = new Request(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(200);
      const body = await response.json();
      expect(body.message).toBe('Folder deleted successfully');
      expect(prisma.folder.delete).toHaveBeenCalledWith({ where: { id: mockFolderId } });
    });

    it('should return 500 for database errors during delete check', async () => {
      const dbError = new Error('Find failed');
      (prisma.folder.findUnique as jest.Mock).mockRejectedValue(dbError);
      const request = new Request(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
      const response = await DELETE(request, { params: { folderId: mockFolderId } });
      expect(response.status).toBe(500);
    });

     it('should return 500 for database errors during actual delete', async () => {
        const mockFolder = { id: mockFolderId, userId: mockUserId, _count: { cards: 0, children: 0 } };
        (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockFolder);
        const dbError = new Error('Delete failed');
        (prisma.folder.delete as jest.Mock).mockRejectedValue(dbError);
        const request = new Request(`http://localhost/api/folders/${mockFolderId}`, { method: 'DELETE' });
        const response = await DELETE(request, { params: { folderId: mockFolderId } });
        expect(response.status).toBe(500);
     });

  });
}); 