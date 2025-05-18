import { PUT } from '@/app/api/cards/[cardId]/route'; // Corrected import names
import { getCurrentUserId } from '@/lib/sessionUtils';
import { NextRequest } from 'next/server'; // Corrected import name, added NextRequest
// PrismaClient and jest-mock-extended types are not needed here if mock is global
// import { PrismaClient } from '@prisma/client'; 
// import { mockDeep, mockReset, DeepMockProxy } from 'jest-mock-extended';

// --- In-File Prisma Mock REMOVED --- 
// All backend tests will now use the global mock from jest.setup.backend.mjs

import prisma from '@/lib/prisma'; // This will now use the global mock setup

jest.mock('@/lib/sessionUtils', () => ({
  getCurrentUserId: jest.fn(),
}));

describe('API /api/cards/[cardId]', () => {
  const mockUserId = 'user-card-dynamic-123';
  const mockCardId = 'cmao1cicq0001u5js1dklafr0';
  const mockFolderId = 'cmao1cph90004u5jsmlpf0lku';
  const otherUserFolderId = 'cmao3szy30001u5v84edvgpgj';

  beforeEach(() => {
    // jest.clearAllMocks(); // This is typically done by mockReset or in global setup
    // mockReset(actualPrismaMockInstance); // Removed, global mock handles reset
    
    // Re-apply $transaction mock if needed on the global prisma instance (if it gets cleared)
    // This might be managed by the global setup, or might need to be ensured here if tests specifically affect it.
    // For now, assume global setup handles the prisma instance and its $transaction mock reset and re-application.

    (getCurrentUserId as jest.Mock).mockReset();
    (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
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
      const request = new NextRequest(`http://localhost/api/cards/${mockCardId}`, { 
        method: 'PUT',
        body: JSON.stringify(validUpdatePayload)
      });
      const response = await PUT(request, { params: Promise.resolve({ cardId: mockCardId }) });
      expect(response.status).toBe(404);
      expect(prisma.knowledgeCard.findUnique).toHaveBeenCalledWith({
         where: { id: mockCardId, userId: mockUserId },
         include: { imageMetadata: { select: { gcsPath: true } } }, 
      });
    });

    it('should return 400 if moving card to a non-existent folder', async () => {
        const mockExistingCard = { id: mockCardId, userId: mockUserId };
        (prisma.knowledgeCard.findUnique as jest.Mock).mockResolvedValue(mockExistingCard);
        (prisma.folder.findUnique as jest.Mock).mockResolvedValue(null); // Target folder not found

        const request = new NextRequest(`http://localhost/api/cards/${mockCardId}`, { // Use NextRequest
            method: 'PUT',
            body: JSON.stringify({ folderId: mockFolderId })
        });
        const response = await PUT(request, { params: Promise.resolve({ cardId: mockCardId }) }); // Wrap params
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

       const request = new NextRequest(`http://localhost/api/cards/${mockCardId}`, { // Use NextRequest
           method: 'PUT',
           body: JSON.stringify({ folderId: otherUserFolderId })
       });
       const response = await PUT(request, { params: Promise.resolve({ cardId: mockCardId }) }); // Wrap params
       expect(response.status).toBe(400);
       const body = await response.json();
       expect(body.error).toContain('Target folder not found or not owned');
       expect(prisma.folder.findUnique).toHaveBeenCalledWith({
            where: { id: otherUserFolderId, userId: mockUserId },
            select: { id: true },
       });
    });

    it('should update card title successfully', async () => {
      const mockExistingCard = { id: mockCardId, userId: mockUserId, imageMetadata: [] };
      const mockUpdatedCard = { ...mockExistingCard, title: validUpdatePayload.title };
      (prisma.knowledgeCard.findUnique as jest.Mock).mockResolvedValue(mockExistingCard);
      (prisma.knowledgeCard.update as jest.Mock).mockResolvedValue(mockUpdatedCard);

      const request = new NextRequest(`http://localhost/api/cards/${mockCardId}`, { // Use NextRequest
        method: 'PUT',
        body: JSON.stringify(validUpdatePayload)
      });
      const response = await PUT(request, { params: Promise.resolve({ cardId: mockCardId }) }); // Wrap params
      expect(response.status).toBe(200);
      const body = await response.json();
      expect(body.title).toBe(validUpdatePayload.title);
      expect(prisma.knowledgeCard.update).toHaveBeenCalledWith(expect.objectContaining({
        where: { id: mockCardId },
        data: { title: validUpdatePayload.title },
      }));
    });

    it('should move card to a valid folder successfully', async () => {
      const mockExistingCard = { id: mockCardId, userId: mockUserId, imageMetadata: [] };
      const mockTargetFolder = { id: mockFolderId, userId: mockUserId };
      const mockUpdatedCardResult = { ...mockExistingCard, folderId: mockFolderId, folder: mockTargetFolder, tags: [] };
      
      (prisma.knowledgeCard.findUnique as jest.Mock).mockResolvedValue(mockExistingCard);
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockTargetFolder); 
      (prisma.knowledgeCard.update as jest.Mock).mockResolvedValue(mockUpdatedCardResult);

      const request = new NextRequest(`http://localhost/api/cards/${mockCardId}`, {
        method: 'PUT',
        body: JSON.stringify(validMovePayload)
      });
      const response = await PUT(request, { params: Promise.resolve({ cardId: mockCardId }) });
      expect(response.status).toBe(200);
      const body = await response.json();
      expect(body.folderId).toBe(mockFolderId);
      expect(prisma.knowledgeCard.update).toHaveBeenCalledWith({
        where: { id: mockCardId },
        data: { folder: { connect: { id: mockFolderId } } }, // Corrected data structure
        include: { tags: true, folder: true, imageMetadata: true }, // Added include to match route
      });
    });

     it('should move card to root (remove folder) successfully', async () => {
       const mockExistingCard = { id: mockCardId, userId: mockUserId, folderId: mockFolderId, imageMetadata: [] };
       const mockUpdatedCardResult = { ...mockExistingCard, folderId: null, folder: null, tags: [] };

       (prisma.knowledgeCard.findUnique as jest.Mock).mockResolvedValue(mockExistingCard);
       (prisma.knowledgeCard.update as jest.Mock).mockResolvedValue(mockUpdatedCardResult);

       const request = new NextRequest(`http://localhost/api/cards/${mockCardId}`, {
         method: 'PUT',
         body: JSON.stringify(validRemoveFolderPayload)
       });
       const response = await PUT(request, { params: Promise.resolve({ cardId: mockCardId }) });
       expect(response.status).toBe(200);
       const body = await response.json();
       expect(body.folderId).toBeNull();
       expect(prisma.knowledgeCard.update).toHaveBeenCalledWith({
         where: { id: mockCardId },
         data: { folder: { disconnect: true } }, // Corrected data structure
         include: { tags: true, folder: true, imageMetadata: true }, // Added include to match route
       });
       expect(prisma.folder.findUnique).not.toHaveBeenCalled(); 
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