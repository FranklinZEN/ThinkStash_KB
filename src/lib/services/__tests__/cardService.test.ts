import {
  getCardLogic,
  updateCardLogic,
  deleteCardLogic,
  CardServicePrismaSubset,
  UpdateCardData,
} from '../cardService';
// import { ServiceResult } from '@/lib/services/serviceUtils'; // Unused
// import { Prisma } from '@prisma/client'; // Unused

// Mock Prisma operations
const mockKnowledgeCardFindUnique = jest.fn();
const mockKnowledgeCardUpdate = jest.fn();
const mockKnowledgeCardDelete = jest.fn();
const mockFolderFindUnique = jest.fn();

const mockPrismaInstance: CardServicePrismaSubset = {
  knowledgeCard: {
    findUnique: mockKnowledgeCardFindUnique,
    update: mockKnowledgeCardUpdate,
    delete: mockKnowledgeCardDelete,
  },
  folder: {
    findUnique: mockFolderFindUnique,
  },
};

const MOCK_USER_ID = 'user-card-test-123';
const MOCK_CARD_ID = 'card-cuid-123';

describe('cardService', () => {
  beforeEach(() => {
    mockKnowledgeCardFindUnique.mockReset();
    mockKnowledgeCardUpdate.mockReset();
    mockKnowledgeCardDelete.mockReset();
    mockFolderFindUnique.mockReset();
  });

  // --- Tests for getCardLogic ---
  describe('getCardLogic', () => {
    it('should return a card if found and owned by user', async () => {
      const mockCard = {
        id: MOCK_CARD_ID,
        userId: MOCK_USER_ID,
        title: 'Test Card',
        folder: null,
        tags: [],
      };
      mockKnowledgeCardFindUnique.mockResolvedValue(mockCard);
      const result = await getCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        mockPrismaInstance,
      );
      expect(mockKnowledgeCardFindUnique).toHaveBeenCalledWith({
        where: { id: MOCK_CARD_ID, userId: MOCK_USER_ID },
        include: { folder: true, tags: true },
      });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockCard);
      expect(result.status).toBe(200);
    });
    it('should return 404 if card not found', async () => {
      mockKnowledgeCardFindUnique.mockResolvedValue(null);
      const result = await getCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        mockPrismaInstance,
      );
      expect(result.success).toBe(false);
      expect(result.error).toBe('Card not found or access denied');
      expect(result.status).toBe(404);
    });
    it('should return 500 on Prisma error', async () => {
      mockKnowledgeCardFindUnique.mockRejectedValue(new Error('DB Error'));
      const result = await getCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        mockPrismaInstance,
      );
      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to retrieve card.');
      expect(result.status).toBe(500);
    });
  });

  // --- Tests for updateCardLogic ---
  describe('updateCardLogic', () => {
    const updateData: UpdateCardData = { title: 'Updated Title' };
    const mockExistingCard = { id: MOCK_CARD_ID, userId: MOCK_USER_ID };

    it('should update a card successfully', async () => {
      const updatedCardData = {
        ...mockExistingCard,
        ...updateData,
        folder: null,
        tags: [],
      };
      mockKnowledgeCardFindUnique.mockResolvedValue(mockExistingCard); // For ownership check
      mockKnowledgeCardUpdate.mockResolvedValue(updatedCardData);
      const result = await updateCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        updateData,
        mockPrismaInstance,
      );
      expect(mockKnowledgeCardFindUnique).toHaveBeenCalledWith({
        where: { id: MOCK_CARD_ID, userId: MOCK_USER_ID },
        select: { id: true },
      });
      expect(mockKnowledgeCardUpdate).toHaveBeenCalledWith({
        where: { id: MOCK_CARD_ID },
        data: { title: 'Updated Title' },
        include: { tags: true, folder: true },
      });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(updatedCardData);
      expect(result.status).toBe(200);
    });

    it('should return 404 if card to update is not found or not owned', async () => {
      mockKnowledgeCardFindUnique.mockResolvedValue(null); // Card not found for ownership check
      const result = await updateCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        updateData,
        mockPrismaInstance,
      );
      expect(result.success).toBe(false);
      expect(result.error).toBe('Card not found or not owned by user');
      expect(result.status).toBe(404);
      expect(mockKnowledgeCardUpdate).not.toHaveBeenCalled();
    });

    it('should handle folder connection and tag updates', async () => {
      const folderId = 'folder-cuid-123';
      const tags = ['tag1', ' Tag2 '];
      const specificUpdateData: UpdateCardData = {
        folderId,
        tags,
        title: 'Card with Folder and Tags',
      };
      const expectedPrismaUpdatePayload = {
        title: 'Card with Folder and Tags',
        folder: { connect: { id: folderId } },
        tags: {
          set: [],
          connectOrCreate: [
            { where: { name: 'tag1' }, create: { name: 'tag1' } },
            { where: { name: 'Tag2' }, create: { name: 'Tag2' } },
          ],
        },
      };
      mockKnowledgeCardFindUnique.mockResolvedValueOnce(mockExistingCard); // For card ownership
      mockFolderFindUnique.mockResolvedValue({ id: folderId }); // For folder ownership
      mockKnowledgeCardUpdate.mockResolvedValue({
        id: MOCK_CARD_ID,
        ...specificUpdateData,
        folder: { id: folderId, name: 'Test Folder' },
        tags: [
          { id: 't1', name: 'tag1' },
          { id: 't2', name: 'Tag2' },
        ],
      });

      const result = await updateCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        specificUpdateData,
        mockPrismaInstance,
      );
      expect(mockFolderFindUnique).toHaveBeenCalledWith({
        where: { id: folderId, userId: MOCK_USER_ID },
        select: { id: true },
      });
      expect(mockKnowledgeCardUpdate).toHaveBeenCalledWith({
        where: { id: MOCK_CARD_ID },
        data: expectedPrismaUpdatePayload,
        include: { tags: true, folder: true },
      });
      expect(result.success).toBe(true);
      expect(result.status).toBe(200);
    });

    it('should return 400 if target folder for update is not found or not owned', async () => {
      const specificUpdateData: UpdateCardData = {
        folderId: 'non-existent-folder',
      };
      mockKnowledgeCardFindUnique.mockResolvedValue(mockExistingCard);
      mockFolderFindUnique.mockResolvedValue(null); // Target folder not found

      const result = await updateCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        specificUpdateData,
        mockPrismaInstance,
      );
      expect(result.success).toBe(false);
      expect(result.error).toBe('Target folder not found or not owned by user');
      expect(result.status).toBe(400);
    });

    it('should return 500 on general Prisma update error', async () => {
      mockKnowledgeCardFindUnique.mockResolvedValue(mockExistingCard);
      mockKnowledgeCardUpdate.mockRejectedValue(new Error('DB Update Error'));
      const result = await updateCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        updateData,
        mockPrismaInstance,
      );
      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to update card.');
      expect(result.details).toBe('DB Update Error');
      expect(result.status).toBe(500);
    });
  });

  // --- Tests for deleteCardLogic ---
  describe('deleteCardLogic', () => {
    const mockExistingCard = { id: MOCK_CARD_ID, userId: MOCK_USER_ID };
    it('should delete a card successfully if found and owned', async () => {
      mockKnowledgeCardFindUnique.mockResolvedValue(mockExistingCard); // For ownership check
      mockKnowledgeCardDelete.mockResolvedValue({
        ...mockExistingCard,
        title: 'Deleted Card',
      } as KnowledgeCard);
      const result = await deleteCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        mockPrismaInstance,
      );
      expect(mockKnowledgeCardFindUnique).toHaveBeenCalledWith({
        where: { id: MOCK_CARD_ID, userId: MOCK_USER_ID },
        select: { id: true },
      });
      expect(mockKnowledgeCardDelete).toHaveBeenCalledWith({
        where: { id: MOCK_CARD_ID },
      });
      expect(result.success).toBe(true);
      expect(result.status).toBe(200);
    });

    it('should return 404 if card to delete is not found or not owned', async () => {
      mockKnowledgeCardFindUnique.mockResolvedValue(null);
      const result = await deleteCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        mockPrismaInstance,
      );
      expect(result.success).toBe(false);
      expect(result.error).toBe('Card not found or not owned by user');
      expect(result.status).toBe(404);
      expect(mockKnowledgeCardDelete).not.toHaveBeenCalled();
    });

    it('should return 500 on Prisma delete error', async () => {
      mockKnowledgeCardFindUnique.mockResolvedValue(mockExistingCard);
      mockKnowledgeCardDelete.mockRejectedValue(new Error('DB Delete Error'));
      const result = await deleteCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        mockPrismaInstance,
      );
      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to delete card.');
      expect(result.details).toBe('DB Delete Error');
      expect(result.status).toBe(500);
    });
  });
});
