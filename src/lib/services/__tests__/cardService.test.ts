import {
  getCardLogic,
  updateCardLogic,
  deleteCardLogic,
  CardServicePrismaSubset,
  UpdateCardData,
} from '../cardService';
import { vi } from 'vitest'; // Import vi
import { PrismaClient } from '@prisma/client'; // Unused

// Mock Prisma operations using vi.fn()
const mockKnowledgeCardFindUnique = vi.fn();
const mockKnowledgeCardUpdate = vi.fn();
const mockKnowledgeCardDelete = vi.fn();
const mockFolderFindUnique = vi.fn();

const mockPrismaInstanceSubset: CardServicePrismaSubset = {
  knowledgeCard: {
    findUnique: mockKnowledgeCardFindUnique,
    update: mockKnowledgeCardUpdate,
    delete: mockKnowledgeCardDelete,
  },
  folder: {
    findUnique: mockFolderFindUnique,
  },
};

// Cast the subset to unknown, then to PrismaClient for use in service calls
const mockPrismaInstance = mockPrismaInstanceSubset as unknown as PrismaClient;

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
    const mockExistingCardForOwnershipCheck = {
      id: MOCK_CARD_ID,
      userId: MOCK_USER_ID,
    };

    it('should update a card successfully', async () => {
      // This is the expected shape of the card *after* update and *after* the final re-fetch
      const expectedCardAfterUpdateAndRefetch = {
        id: MOCK_CARD_ID,
        userId: MOCK_USER_ID,
        title: 'Updated Title', // from updateData
        folder: null, // assuming default
        tags: [], // assuming default
        content: null, // assuming not updated, so whatever it was or null
        isStarred: false, // assuming default
        createdAt: expect.any(Date), // Or a fixed mock date
        updatedAt: expect.any(Date), // Or a fixed mock date
        folderId: null, // assuming default
      };

      mockKnowledgeCardFindUnique
        .mockResolvedValueOnce(mockExistingCardForOwnershipCheck) // For ownership check
        .mockResolvedValueOnce(expectedCardAfterUpdateAndRefetch); // For the re-fetch at the end

      // The .update() call itself will resolve to something.
      // For this test, the crucial part is what the subsequent findUnique (re-fetch) returns.
      // Let's make .update() also resolve to this shape for mock consistency.
      mockKnowledgeCardUpdate.mockResolvedValue(
        expectedCardAfterUpdateAndRefetch,
      );

      const result = await updateCardLogic(
        MOCK_CARD_ID,
        MOCK_USER_ID,
        updateData, // Contains only { title: 'Updated Title' }
        mockPrismaInstance,
      );
      expect(mockKnowledgeCardFindUnique).toHaveBeenCalledTimes(2); // Once for ownership, once for re-fetch
      expect(mockKnowledgeCardUpdate).toHaveBeenCalledWith({
        where: { id: MOCK_CARD_ID, userId: MOCK_USER_ID },
        data: { title: 'Updated Title' }, // This is the actual payload for .update()
        include: { tags: true, folder: true },
      });
      expect(result.success).toBe(true);
      // result.data should now match expectedCardAfterUpdateAndRefetch due to the second mockResolvedValueOnce for findUnique
      expect(result.data).toEqual(expectedCardAfterUpdateAndRefetch);
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
      const tagsToConnect = ['tag1', 'Tag2']; // Names of tags
      const specificUpdateData: UpdateCardData = {
        folderId,
        tags: tagsToConnect,
        title: 'Card with Folder and Tags',
      };

      // Expected shape of the card *after* update and *after* the final re-fetch
      const expectedCardAfterUpdateAndRefetchWithRelations = {
        id: MOCK_CARD_ID,
        userId: MOCK_USER_ID,
        title: 'Card with Folder and Tags',
        folderId: folderId,
        folder: { id: folderId, name: 'Mocked Test Folder Name' }, // Mocked folder object
        tags: [
          // Mocked tag objects
          { id: 't1', name: 'tag1' },
          { id: 't2', name: 'Tag2' },
        ],
        content: null,
        isStarred: false,
        createdAt: expect.any(Date),
        updatedAt: expect.any(Date),
      };

      mockKnowledgeCardFindUnique
        .mockResolvedValueOnce(mockExistingCardForOwnershipCheck) // 1. For card ownership check
        .mockResolvedValueOnce(expectedCardAfterUpdateAndRefetchWithRelations); // 2. For the re-fetch at the end

      mockFolderFindUnique.mockResolvedValue({ id: folderId }); // For folder ownership check (passes)

      // The .update() call itself. For this test, the crucial part is what the subsequent findUnique (re-fetch) returns.
      // Let it resolve to the same shape for mock consistency.
      mockKnowledgeCardUpdate.mockResolvedValue(
        expectedCardAfterUpdateAndRefetchWithRelations,
      );

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
        where: { id: MOCK_CARD_ID, userId: MOCK_USER_ID },
        data: {
          // This is the actual data payload for the .update() operation
          title: 'Card with Folder and Tags',
          folder: { connect: { id: folderId } },
          tags: {
            set: [],
            connectOrCreate: [
              { where: { name: 'tag1' }, create: { name: 'tag1' } },
              { where: { name: 'Tag2' }, create: { name: 'Tag2' } },
            ],
          },
        },
        include: { tags: true, folder: true },
      });
      expect(result.success).toBe(true);
      // result.data should now match due to the second mockResolvedValueOnce for findUnique
      expect(result.data).toEqual(
        expectedCardAfterUpdateAndRefetchWithRelations,
      );
      expect(result.status).toBe(200);
    });

    it('should return 400 if target folder for update is not found or not owned', async () => {
      const specificUpdateData: UpdateCardData = {
        folderId: 'non-existent-folder',
      };
      mockKnowledgeCardFindUnique.mockResolvedValue(
        mockExistingCardForOwnershipCheck,
      );
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
      mockKnowledgeCardFindUnique.mockResolvedValue(
        mockExistingCardForOwnershipCheck,
      );
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
