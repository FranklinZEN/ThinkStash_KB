/**
 * @vitest-environment node 
 */
import {
  getCardLogic,
  updateCardLogic,
  deleteCardLogic,
  UpdateCardData,
  handleCardImageAssociations, 
} from '@/lib/services/cardService';
import { vi, Mock } from 'vitest';

import {
  mockKnowledgeCardFindUnique,
  mockKnowledgeCardUpdate,
  mockKnowledgeCardDelete,
  mockFolderFindUnique,
  mockImageRecordCreate, 
  mockImageRecordUpdate, 
  mockImageRecordUpdateMany, 
  mockGCSUploadFile,      
} from '@/tests/helpers/apiTestSetup';

const MOCK_USER_ID = 'user-card-test-123';
const MOCK_CARD_ID = 'card-cuid-123';

describe('cardService', () => {
  beforeEach(() => {
    mockKnowledgeCardFindUnique.mockReset();
    mockKnowledgeCardUpdate.mockReset();
    mockKnowledgeCardDelete.mockReset();
    mockFolderFindUnique.mockReset();
    mockImageRecordCreate.mockReset();
    mockImageRecordUpdate.mockReset();
    mockImageRecordUpdateMany.mockReset();
    mockGCSUploadFile.mockReset();
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
        content: null, 
        isStarred: false, 
        createdAt: new Date(), 
        updatedAt: new Date(), 
        folderId: null, 
      };
      mockKnowledgeCardFindUnique.mockResolvedValue(mockCard);
      const result = await getCardLogic(MOCK_CARD_ID, MOCK_USER_ID);
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
      const result = await getCardLogic(MOCK_CARD_ID, MOCK_USER_ID);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Card not found or access denied');
      expect(result.status).toBe(404);
    });
    it('should return 500 on Prisma error', async () => {
      mockKnowledgeCardFindUnique.mockRejectedValue(new Error('DB Error'));
      const result = await getCardLogic(MOCK_CARD_ID, MOCK_USER_ID);
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
      const expectedCardAfterUpdateAndRefetch = {
        id: MOCK_CARD_ID, userId: MOCK_USER_ID, title: 'Updated Title', 
        folder: null, tags: [], content: null, isStarred: false, 
        createdAt: expect.any(Date), updatedAt: expect.any(Date), folderId: null,
      };
      mockKnowledgeCardFindUnique
        .mockResolvedValueOnce(mockExistingCardForOwnershipCheck) 
        .mockResolvedValueOnce(expectedCardAfterUpdateAndRefetch); 
      mockKnowledgeCardUpdate.mockResolvedValue(expectedCardAfterUpdateAndRefetch);

      const result = await updateCardLogic(MOCK_CARD_ID,MOCK_USER_ID,updateData);
      expect(mockKnowledgeCardFindUnique).toHaveBeenCalledTimes(2);
      expect(mockKnowledgeCardUpdate).toHaveBeenCalledWith({
        where: { id: MOCK_CARD_ID, userId: MOCK_USER_ID },
        data: { title: 'Updated Title' },
      });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(expectedCardAfterUpdateAndRefetch);
      expect(result.status).toBe(200);
    });

    it('should return 404 if card to update is not found or not owned', async () => {
      mockKnowledgeCardFindUnique.mockResolvedValue(null); 
      const result = await updateCardLogic(MOCK_CARD_ID, MOCK_USER_ID, updateData);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Card not found or not owned by user');
      expect(result.status).toBe(404);
      expect(mockKnowledgeCardUpdate).not.toHaveBeenCalled();
    });

    it('should handle folder connection and tag updates', async () => {
      const folderId = 'folder-cuid-123';
      const tagsToConnect = ['tag1', 'Tag2'];
      const specificUpdateData: UpdateCardData = { folderId, tags: tagsToConnect, title: 'Card with Folder and Tags' };
      const expectedCardAfterUpdate = {
        id: MOCK_CARD_ID, userId: MOCK_USER_ID, title: 'Card with Folder and Tags',
        folderId: folderId, folder: { id: folderId, name: 'Mocked Test Folder Name' },
        tags: [ { id: 't1', name: 'tag1' }, { id: 't2', name: 'Tag2' } ],
        content: null, isStarred: false, createdAt: expect.any(Date), updatedAt: expect.any(Date),
      };

      mockKnowledgeCardFindUnique
        .mockResolvedValueOnce(mockExistingCardForOwnershipCheck)
        .mockResolvedValueOnce(expectedCardAfterUpdate); 
      mockFolderFindUnique.mockResolvedValue({ id: folderId }); 
      mockKnowledgeCardUpdate.mockResolvedValue(expectedCardAfterUpdate);

      const result = await updateCardLogic(MOCK_CARD_ID, MOCK_USER_ID, specificUpdateData);

      expect(mockFolderFindUnique).toHaveBeenCalledWith({ where: { id: folderId, userId: MOCK_USER_ID }, select: { id: true } });
      expect(mockKnowledgeCardUpdate).toHaveBeenCalledWith({
        where: { id: MOCK_CARD_ID, userId: MOCK_USER_ID },
        data: {
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
      });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(expectedCardAfterUpdate);
      expect(result.status).toBe(200);
    });

    it('should return 400 if target folder for update is not found or not owned', async () => {
      const specificUpdateData: UpdateCardData = { folderId: 'non-existent-folder' };
      mockKnowledgeCardFindUnique.mockResolvedValue(mockExistingCardForOwnershipCheck);
      mockFolderFindUnique.mockResolvedValue(null); 
      const result = await updateCardLogic(MOCK_CARD_ID, MOCK_USER_ID, specificUpdateData);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Target folder not found or not owned by user');
      expect(result.status).toBe(400);
    });

    it('should return 500 on general Prisma update error', async () => {
      mockKnowledgeCardFindUnique.mockResolvedValue(mockExistingCardForOwnershipCheck);
      mockKnowledgeCardUpdate.mockRejectedValue(new Error('DB Update Error'));
      const result = await updateCardLogic(MOCK_CARD_ID, MOCK_USER_ID, updateData);
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
      mockKnowledgeCardFindUnique.mockResolvedValue(mockExistingCard); 
      mockKnowledgeCardDelete.mockResolvedValue({ ...mockExistingCard, title: 'Deleted Card' } as any);
      const result = await deleteCardLogic(MOCK_CARD_ID, MOCK_USER_ID);
      expect(mockKnowledgeCardFindUnique).toHaveBeenCalledWith({
        where: { id: MOCK_CARD_ID, userId: MOCK_USER_ID },
        select: { id: true },
      });
      expect(mockKnowledgeCardDelete).toHaveBeenCalledWith({ where: { id: MOCK_CARD_ID } });
      expect(result.success).toBe(true);
      expect(result.status).toBe(200);
    });

    it('should return 404 if card to delete is not found or not owned', async () => {
      mockKnowledgeCardFindUnique.mockResolvedValue(null);
      const result = await deleteCardLogic(MOCK_CARD_ID, MOCK_USER_ID);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Card not found or not owned by user');
      expect(result.status).toBe(404);
      expect(mockKnowledgeCardDelete).not.toHaveBeenCalled();
    });

    it('should return 500 on Prisma delete error', async () => {
      mockKnowledgeCardFindUnique.mockResolvedValue(mockExistingCard);
      mockKnowledgeCardDelete.mockRejectedValue(new Error('DB Delete Error'));
      const result = await deleteCardLogic(MOCK_CARD_ID, MOCK_USER_ID);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to delete card.');
      expect(result.details).toBe('DB Delete Error');
      expect(result.status).toBe(500);
    });
  });

}); 