import { PUT, DELETE, GET } from '@/app/api/cards/[cardId]/route'; // Import handlers
import { prisma } from '@/lib/prisma';
import { getCurrentUserId } from '@/lib/sessionUtils';
import { NextResponse } from 'next/server';
import { Prisma } from '@prisma/client';

// Mock dependencies
jest.mock('@/lib/prisma', () => ({
  prisma: {
    knowledgeCard: { // Changed from 'card' to match schema?
      findUnique: jest.fn(),
      update: jest.fn(),
      delete: jest.fn(),
    },
    folder: { // Need to mock folder for ownership check
        findUnique: jest.fn(),
    }
  },
}));

jest.mock('@/lib/sessionUtils', () => ({
  getCurrentUserId: jest.fn(),
}));

describe('API /api/cards/[cardId]', () => {
  const mockUserId = 'user-card-dynamic-123';
  const mockCardId = 'card-cuid-456';
  const mockFolderId = 'folder-cuid-789';
  const otherUserFolderId = 'folder-cuid-other';

  beforeEach(() => {
    jest.clearAllMocks();
    (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId); // Assume logged in
  });

  // --- GET Tests ---
  describe('GET', () => {
     // ... Add GET tests similar to folder GET tests ...
     // Test success, not found/owned, unauthenticated, invalid ID
  });

  // --- PUT (Update/Move) Tests ---
  describe('PUT', () => {
    const validUpdatePayload = { title: 'Updated Title' };
    const validMovePayload = { folderId: mockFolderId };
    const validRemoveFolderPayload = { folderId: null };

    // ... Add tests for 400 invalid cardId, 401 unauthenticated, 400 invalid body (no fields) ...

    it('should return 404 if card not found or not owned', async () => {
      (prisma.knowledgeCard.findUnique as jest.Mock).mockResolvedValue(null);
      const request = new Request(`http://localhost/api/cards/${mockCardId}`, {
        method: 'PUT',
        body: JSON.stringify(validUpdatePayload)
      });
      const response = await PUT(request, { params: { cardId: mockCardId } });
      expect(response.status).toBe(404);
      expect(prisma.knowledgeCard.findUnique).toHaveBeenCalledWith({
         where: { id: mockCardId, userId: mockUserId },
         select: { id: true },
      });
    });

    it('should return 400 if moving card to a non-existent folder', async () => {
        const mockExistingCard = { id: mockCardId, userId: mockUserId };
        (prisma.knowledgeCard.findUnique as jest.Mock).mockResolvedValue(mockExistingCard);
        (prisma.folder.findUnique as jest.Mock).mockResolvedValue(null); // Target folder not found

        const request = new Request(`http://localhost/api/cards/${mockCardId}`, {
            method: 'PUT',
            body: JSON.stringify({ folderId: mockFolderId })
        });
        const response = await PUT(request, { params: { cardId: mockCardId } });
        expect(response.status).toBe(400);
        const body = await response.json();
        expect(body.error).toContain('Target folder not found');
        expect(prisma.folder.findUnique).toHaveBeenCalledWith({
            where: { id: mockFolderId, userId: mockUserId },
            select: { id: true },
        });
     });

    it('should return 400 if moving card to a folder owned by another user', async () => {
       const mockExistingCard = { id: mockCardId, userId: mockUserId };
       (prisma.knowledgeCard.findUnique as jest.Mock).mockResolvedValue(mockExistingCard);
       // Simulate folder findUnique returning null because userId doesn't match
       (prisma.folder.findUnique as jest.Mock).mockResolvedValue(null); 

       const request = new Request(`http://localhost/api/cards/${mockCardId}`, {
           method: 'PUT',
           body: JSON.stringify({ folderId: otherUserFolderId })
       });
       const response = await PUT(request, { params: { cardId: mockCardId } });
       expect(response.status).toBe(400);
       const body = await response.json();
       expect(body.error).toContain('Target folder not found or not owned');
       expect(prisma.folder.findUnique).toHaveBeenCalledWith({
            where: { id: otherUserFolderId, userId: mockUserId },
            select: { id: true },
       });
    });

    it('should update card title successfully', async () => {
      const mockExistingCard = { id: mockCardId, userId: mockUserId };
      const mockUpdatedCard = { ...mockExistingCard, title: validUpdatePayload.title };
      (prisma.knowledgeCard.findUnique as jest.Mock).mockResolvedValue(mockExistingCard);
      (prisma.knowledgeCard.update as jest.Mock).mockResolvedValue(mockUpdatedCard);

      const request = new Request(`http://localhost/api/cards/${mockCardId}`, {
        method: 'PUT',
        body: JSON.stringify(validUpdatePayload)
      });
      const response = await PUT(request, { params: { cardId: mockCardId } });
      expect(response.status).toBe(200);
      const body = await response.json();
      expect(body.title).toBe(validUpdatePayload.title);
      expect(prisma.knowledgeCard.update).toHaveBeenCalledWith(expect.objectContaining({
        where: { id: mockCardId },
        data: { title: validUpdatePayload.title },
      }));
    });

    it('should move card to a valid folder successfully', async () => {
      const mockExistingCard = { id: mockCardId, userId: mockUserId };
      const mockTargetFolder = { id: mockFolderId, userId: mockUserId };
      const mockUpdatedCard = { ...mockExistingCard, folderId: mockFolderId };
      (prisma.knowledgeCard.findUnique as jest.Mock).mockResolvedValue(mockExistingCard);
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockTargetFolder); // Target folder exists and is owned
      (prisma.knowledgeCard.update as jest.Mock).mockResolvedValue(mockUpdatedCard);

      const request = new Request(`http://localhost/api/cards/${mockCardId}`, {
        method: 'PUT',
        body: JSON.stringify(validMovePayload)
      });
      const response = await PUT(request, { params: { cardId: mockCardId } });
      expect(response.status).toBe(200);
      const body = await response.json();
      expect(body.folderId).toBe(mockFolderId);
      expect(prisma.knowledgeCard.update).toHaveBeenCalledWith(expect.objectContaining({
        where: { id: mockCardId },
        data: { folderId: mockFolderId },
      }));
    });

     it('should move card to root (remove folder) successfully', async () => {
       const mockExistingCard = { id: mockCardId, userId: mockUserId, folderId: mockFolderId }; // Start in a folder
       const mockUpdatedCard = { ...mockExistingCard, folderId: null };
       (prisma.knowledgeCard.findUnique as jest.Mock).mockResolvedValue(mockExistingCard);
       (prisma.knowledgeCard.update as jest.Mock).mockResolvedValue(mockUpdatedCard);

       const request = new Request(`http://localhost/api/cards/${mockCardId}`, {
         method: 'PUT',
         body: JSON.stringify(validRemoveFolderPayload)
       });
       const response = await PUT(request, { params: { cardId: mockCardId } });
       expect(response.status).toBe(200);
       const body = await response.json();
       expect(body.folderId).toBeNull();
       expect(prisma.knowledgeCard.update).toHaveBeenCalledWith(expect.objectContaining({
         where: { id: mockCardId },
         data: { folderId: null },
       }));
       expect(prisma.folder.findUnique).not.toHaveBeenCalled(); // No folder check needed for null
     });

    // ... Add tests for other update scenarios (content, combined fields) ...
    // ... Add test for 500 errors ...

  });

  // --- DELETE Tests ---
  describe('DELETE', () => {
     // ... Add DELETE tests similar to folder DELETE tests ...
     // Test success, not found/owned, unauthenticated, invalid ID
  });
}); 