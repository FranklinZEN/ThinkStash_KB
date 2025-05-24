/**
 * @vitest-environment node
 */
import request from 'supertest';
import { makeTestServer, TestServer } from '../../../../tests/helpers/testServer';
import {
  MOCK_USER_ID,
  mockKnowledgeCardFindUnique,
  mockKnowledgeCardUpdate,
  mockKnowledgeCardDelete,
  mockUserFindUnique,      
  mockFolderFindUnique,    
  mockImageRecordCreate,
  mockImageRecordUpdate,
  mockImageRecordDeleteMany,
} from '../../../../tests/helpers/apiTestSetup';
import { describe, it, expect, vi, beforeEach, afterAll, beforeAll, Mock } from 'vitest';
import { UpdateCardData } from '@/lib/services/cardService'; 
// import { getServerSession } from 'next-auth/next'; // No longer needed for direct mocking here

let testServer: TestServer;
let currentTestServerUrl: string;

beforeAll(async () => {
  testServer = await makeTestServer();
  currentTestServerUrl = testServer.url;
});

afterAll(async () => {
  if (testServer?.close) {
    await testServer.close();
  }
});

// ADD THIS LOG 
// console.log('[Card Test File DEBUG] mockKnowledgeCardFindUnique upon import:', typeof mockKnowledgeCardFindUnique, mockKnowledgeCardFindUnique);
// console.log('[Card Test File DEBUG] mockKnowledgeCardUpdate upon import:', typeof mockKnowledgeCardUpdate, mockKnowledgeCardUpdate);
// console.log('[Card Test File DEBUG] mockKnowledgeCardDelete upon import:', typeof mockKnowledgeCardDelete, mockKnowledgeCardDelete);

const MOCK_CARD_ID = 'clxkz1g5g000008l4g3z3h2j9'; 
const MOCK_INVALID_CARD_ID = 'invalid-cuid-format'; 

const validUpdatePayload: UpdateCardData = {
  title: 'Updated Test Card Title',
  content: [{ id: 'block-id-for-test', type: 'paragraph', content: [{ type: 'text', text: 'Updated content.' }] }],
  folderId: null, 
  tags: ['updated', 'vitest'],
};

describe('/api/cards/[cardId] API Route Handlers', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockKnowledgeCardFindUnique.mockReset();
    mockKnowledgeCardUpdate.mockReset();
    mockKnowledgeCardDelete.mockReset();
    mockUserFindUnique.mockReset();
    mockFolderFindUnique.mockReset();
    mockImageRecordCreate.mockReset();
    mockImageRecordUpdate.mockReset();
    mockImageRecordDeleteMany.mockReset();
    // (getServerSession as Mock).mockClear(); // No longer needed if not mocking directly in test
  });

  // All tests below will use currentTestServerUrl derived from process.env.TEST_SERVER_URL
  describe('GET handler', () => {
    it('should return 401 if user is not authenticated', async () => {
      // (getServerSession as Mock).mockResolvedValue(null); // No longer needed
      const response = await request(currentTestServerUrl)
        .get(`/api/cards/${MOCK_CARD_ID}`)
        .set('X-Test-User-Id', 'null');
      expect(response.status).toBe(401);
      expect(response.body.error).toBe('Unauthorized');
      expect(mockKnowledgeCardFindUnique).not.toHaveBeenCalled();
    });

    it('should return 400 for invalid card ID format', async () => {
      const response = await request(currentTestServerUrl)
        .get(`/api/cards/${MOCK_INVALID_CARD_ID}`)
        .set('X-Test-User-Id', MOCK_USER_ID);
      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Invalid card ID format'); 
    });

    it('should return card data on successful GET', async () => {
        const cardDataFromMock = { 
            id: MOCK_CARD_ID, 
            title: 'Test Card', 
            userId: MOCK_USER_ID, 
            content: [], 
            tags: [], // Matches include: { tags: true }
            folder: null, // Matches include: { folder: true }
            // Add other fields from KnowledgeCardPayload if necessary for the response shape
            createdAt: new Date(),
            updatedAt: new Date(),
            isPublic: false,
            isArchived: false,
            folderId: null,
            summary: null,
        };
        (mockKnowledgeCardFindUnique as Mock).mockResolvedValue(cardDataFromMock);

        const response = await request(currentTestServerUrl)
            .get(`/api/cards/${MOCK_CARD_ID}`)
            .set('X-Test-User-Id', MOCK_USER_ID);

        expect(response.status).toBe(200);
        // The route returns result.data, which is the cardDataFromMock
        // NextResponse.json will serialize dates
        expect(response.body).toEqual(expect.objectContaining({
            id: MOCK_CARD_ID, 
            title: 'Test Card',
            userId: MOCK_USER_ID,
            tags: [],
            folder: null,
            createdAt: cardDataFromMock.createdAt.toISOString(), // Dates will be serialized
            updatedAt: cardDataFromMock.updatedAt.toISOString(),
        }));
        expect(mockKnowledgeCardFindUnique).toHaveBeenCalledWith({ 
            where: { id: MOCK_CARD_ID, userId: MOCK_USER_ID },
            include: { folder: true, tags: true }
        });
    });

    it('should return 404 if cardService (via Prisma) does not find the card', async () => {
      (mockKnowledgeCardFindUnique as Mock).mockResolvedValue(null);
      // (mockUserFindUnique as Mock).mockResolvedValue({ id: MOCK_USER_ID });

      const response = await request(currentTestServerUrl)
        .get(`/api/cards/${MOCK_CARD_ID}`)
        .set('X-Test-User-Id', MOCK_USER_ID);
      expect(response.status).toBe(404);
      expect(response.body.error).toBe('Card not found or access denied');
    });
  });

  describe('PUT handler', () => {
    it('should return 401 if user is not authenticated', async () => {
      // (getServerSession as Mock).mockResolvedValue(null); // No longer needed
      const response = await request(currentTestServerUrl)
        .put(`/api/cards/${MOCK_CARD_ID}`)
        .set('X-Test-User-Id', 'null')
        .send(validUpdatePayload);
      expect(response.status).toBe(401);
    });
    
    it('should return 400 for invalid card ID format', async () => {
      const response = await request(currentTestServerUrl)
        .put(`/api/cards/${MOCK_INVALID_CARD_ID}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .send(validUpdatePayload);
      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Invalid card ID format'); 
    });

    it('should return 400 for invalid request body', async () => {
      const response = await request(currentTestServerUrl)
        .put(`/api/cards/${MOCK_CARD_ID}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .send({ title: '' }); // Invalid payload
      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Validation failed');
    });

    it('should call cardService.updateCard (via Prisma mocks) and return success', async () => {
      const updatedCardData = { id: MOCK_CARD_ID, ...validUpdatePayload, userId: MOCK_USER_ID, content: validUpdatePayload.content as Prisma.JsonValue, tags: [{name: 'updated'}, {name: 'vitest'}] }; // Adjust shape for service return
      
      // Mock for initial findUnique in updateCardLogic
      (mockKnowledgeCardFindUnique as Mock).mockResolvedValueOnce({ id: MOCK_CARD_ID, userId: MOCK_USER_ID, title: 'Old Title' });
      // Mock for folder check if folderId is provided (it's null in validUpdatePayload, so this might not be called or needs specific mock if called with null)
      if (validUpdatePayload.folderId) {
        (mockFolderFindUnique as Mock).mockResolvedValue({ id: validUpdatePayload.folderId, userId: MOCK_USER_ID });
      } else {
        mockFolderFindUnique.mockResolvedValue(null); // Or ensure it's not called
      }
      // Mock for the actual update operation
      (mockKnowledgeCardUpdate as Mock).mockResolvedValue(updatedCardData);
      // Mock for the re-fetch after update
      (mockKnowledgeCardFindUnique as Mock).mockResolvedValueOnce(updatedCardData);

      const response = await request(currentTestServerUrl)
        .put(`/api/cards/${MOCK_CARD_ID}`)
        .set('X-Test-User-Id', MOCK_USER_ID)
        .send(validUpdatePayload);

      expect(response.status).toBe(200);
      // Ensure response body matches the shape returned by the service, which now includes folder and tags objects
      expect(response.body).toEqual(expect.objectContaining({ id: MOCK_CARD_ID, title: validUpdatePayload.title })); 
      expect(mockKnowledgeCardUpdate).toHaveBeenCalledWith(expect.objectContaining({ 
        where: { id: MOCK_CARD_ID, userId: MOCK_USER_ID }, 
        // data will be more complex due to content processing and tag connectOrCreate
      }));
    });
  });

  describe('DELETE handler', () => {
    it('should return 401 if user is not authenticated', async () => {
      // (getServerSession as Mock).mockResolvedValue(null); // No longer needed
      const response = await request(currentTestServerUrl)
        .delete(`/api/cards/${MOCK_CARD_ID}`)
        .set('X-Test-User-Id', 'null');
      expect(response.status).toBe(401);
    });

    it('should return 400 for invalid card ID format', async () => {
      const response = await request(currentTestServerUrl)
        .delete(`/api/cards/${MOCK_INVALID_CARD_ID}`)
        .set('X-Test-User-Id', MOCK_USER_ID);
      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Invalid card ID format');
    });

    it('should call cardService.deleteCard (via Prisma mocks) and return success', async () => {
      // Mock for initial findUnique in deleteCardLogic
      (mockKnowledgeCardFindUnique as Mock).mockResolvedValue({ id: MOCK_CARD_ID, userId: MOCK_USER_ID }); 
      // Mock for the actual delete operation
      (mockKnowledgeCardDelete as Mock).mockResolvedValue({ id: MOCK_CARD_ID });

      const response = await request(currentTestServerUrl)
        .delete(`/api/cards/${MOCK_CARD_ID}`)
        .set('X-Test-User-Id', MOCK_USER_ID);

      expect(response.status).toBe(200);
      expect(response.body.message).toBe('Card deleted successfully');
      expect(mockKnowledgeCardDelete).toHaveBeenCalledWith(expect.objectContaining({ where: { id: MOCK_CARD_ID } })); // userId check is in the service before delete
    });
  });
}); 