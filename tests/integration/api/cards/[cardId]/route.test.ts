/**
 * @jest-environment node
 */
import 'next-test-api-route-handler'; // Must be first
import { testApiHandler } from 'next-test-api-route-handler';
import * as cardApiHandlerModule from '@/app/api/cards/[cardId]/route'; // Import API handler at top
import { UpdateCardData } from '@/lib/services/cardService'; // Types can be imported
import { prismaMock } from 'tests/__helpers__/prisma-mock'; 
// Import singleton mock functions (now globally wired up in setup-tests.ts)
import { mockGetCurrentUserId } from 'tests/setup-tests'; 
import { 
  mockGetCardLogic,
  mockUpdateCardLogic,
  mockDeleteCardLogic,
  mockHandleCardImageAssociations
} from 'tests/__helpers__/card-service-mock'; 
import { jest } from '@jest/globals'; // For jest.fn()

const MOCK_USER_ID = 'user-card-test-123';
const MOCK_CARD_ID = 'clxkz1g5g000008l4g3z3h2j9'; 
const MOCK_INVALID_CARD_ID = 'invalid-cuid-format'; 

const validUpdatePayload: UpdateCardData = {
  title: 'Updated Test Card Title',
  content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Updated content.' }] }],
  folderId: null, 
  tags: ['updated', 'jest'],
};

describe('/api/cards/[cardId] integration tests', () => {
  beforeEach(() => {
    // jest.resetAllMocks(); // REMOVE THIS
    
    // Reset mocks imported for this test suite
    mockGetCurrentUserId.mockReset().mockResolvedValue(MOCK_USER_ID); // Set default for auth tests
    mockGetCardLogic.mockReset();
    mockUpdateCardLogic.mockReset();
    mockDeleteCardLogic.mockReset();
    mockHandleCardImageAssociations.mockReset();

    // prismaMock is reset by its own beforeEach in tests/__helpers__/prisma-mock.ts
  });

  describe('GET /api/cards/[cardId]', () => {
    it('should return 401 if user is not authenticated', async () => {
      mockGetCurrentUserId.mockReset().mockResolvedValue(null); // Override for this specific test
      await testApiHandler({
        appHandler: cardApiHandlerModule,
        params: { cardId: MOCK_CARD_ID },
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'GET' });
          const json = await res.json();
          expect(res.status).toBe(401);
          expect(json.error).toBe('Unauthorized');
          expect(mockGetCardLogic).not.toHaveBeenCalled();
        },
      });
    });

    it('should return 400 for invalid card ID format', async () => {
      // mockGetCurrentUserId is already set to MOCK_USER_ID by the outer beforeEach
      await testApiHandler({
        appHandler: cardApiHandlerModule,
        params: { cardId: MOCK_INVALID_CARD_ID },
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'GET' });
          const json = await res.json();
          expect(res.status).toBe(400);
          expect(json.error).toBe('Invalid card ID format');
          expect(mockGetCardLogic).not.toHaveBeenCalled();
        },
      });
    });

    it('should call getCardLogic and return its success response', async () => {
      // mockGetCurrentUserId is already set
      const serviceResponseData = { id: MOCK_CARD_ID, title: 'Test Card' };
      const serviceResult = { success: true, data: serviceResponseData, status: 200 };
      mockGetCardLogic.mockResolvedValue(serviceResult);

      await testApiHandler({
        appHandler: cardApiHandlerModule, 
        params: { cardId: MOCK_CARD_ID },
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'GET' });
          const json = await res.json();
          expect(mockGetCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, prismaMock);
          expect(res.status).toBe(200);
          expect(json).toEqual(serviceResponseData);
        },
      });
    });

    it('should call getCardLogic and return its error response (e.g., 404 not found)', async () => {
      // mockGetCurrentUserId is already set
      const serviceResult = { success: false, error: 'Card not found', status: 404 };
      mockGetCardLogic.mockResolvedValue(serviceResult);

      await testApiHandler({
        appHandler: cardApiHandlerModule, 
        params: { cardId: MOCK_CARD_ID },
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'GET' });
          const json = await res.json();
          expect(mockGetCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, prismaMock);
          expect(res.status).toBe(404);
          expect(json.error).toBe('Card not found');
        },
      });
    });
  });

  describe('PUT /api/cards/[cardId]', () => {
    it('should return 401 if user is not authenticated', async () => {
      mockGetCurrentUserId.mockReset().mockResolvedValue(null); // Override
      await testApiHandler({
        appHandler: cardApiHandlerModule, 
        params: { cardId: MOCK_CARD_ID },
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'PUT', body: JSON.stringify(validUpdatePayload) });
          const json = await res.json();
          expect(res.status).toBe(401);
          expect(json.error).toBe('Unauthorized');
          expect(mockUpdateCardLogic).not.toHaveBeenCalled();
        },
      });
    });
    
    it('should return 400 for invalid card ID format', async () => {
      // mockGetCurrentUserId is already set
      await testApiHandler({
          appHandler: cardApiHandlerModule, 
          params: { cardId: MOCK_INVALID_CARD_ID },
          test: async ({ fetch }) => {
              const res = await fetch({ method: 'PUT', body: JSON.stringify(validUpdatePayload) });
              const json = await res.json();
              expect(res.status).toBe(400);
              expect(json.error).toBe('Invalid card ID format');
          }
      });
    });

    it('should return 400 for invalid request body (Zod validation)', async () => {
      // mockGetCurrentUserId is already set
      await testApiHandler({
        appHandler: cardApiHandlerModule, 
        params: { cardId: MOCK_CARD_ID },
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'PUT', body: JSON.stringify({ title: '' }) }); 
          const json = await res.json();
          expect(res.status).toBe(400);
          expect(json.error).toBe('Validation failed');
          expect(mockUpdateCardLogic).not.toHaveBeenCalled();
        },
      });
    });

    it('should call updateCardLogic and return its success response', async () => {
      // mockGetCurrentUserId is already set
      const serviceResponseData = { id: MOCK_CARD_ID, ...validUpdatePayload };
      const serviceResult = { success: true, data: serviceResponseData, status: 200 };
      mockUpdateCardLogic.mockResolvedValue(serviceResult);

      await testApiHandler({
        appHandler: cardApiHandlerModule, 
        params: { cardId: MOCK_CARD_ID },
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'PUT', body: JSON.stringify(validUpdatePayload) });
          const json = await res.json();
          expect(mockUpdateCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, validUpdatePayload, prismaMock);
          expect(res.status).toBe(200);
          expect(json).toEqual(serviceResponseData);
        },
      });
    });

    it('should call updateCardLogic and return its error response (e.g. 404 card not found by service)', async () => {
      // mockGetCurrentUserId is already set
      const serviceResult = { success: false, error: 'Card not found by service', status: 404 };
      mockUpdateCardLogic.mockResolvedValue(serviceResult);
      await testApiHandler({
          appHandler: cardApiHandlerModule, 
          params: { cardId: MOCK_CARD_ID },
          test: async ({fetch}) => {
              const res = await fetch({ method: 'PUT', body: JSON.stringify(validUpdatePayload) });
              const json = await res.json();
              expect(res.status).toBe(404);
              expect(json.error).toBe('Card not found by service');
          }
      });
    });
  });

  describe('DELETE /api/cards/[cardId]', () => {
    it('should return 401 if user is not authenticated', async () => {
      mockGetCurrentUserId.mockReset().mockResolvedValue(null); // Override
      await testApiHandler({
        appHandler: cardApiHandlerModule, 
        params: { cardId: MOCK_CARD_ID },
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'DELETE' });
          const json = await res.json();
          expect(res.status).toBe(401);
          expect(json.error).toBe('Unauthorized');
          expect(mockDeleteCardLogic).not.toHaveBeenCalled();
        },
      });
    });

    it('should return 400 for invalid card ID format', async () => {
      // mockGetCurrentUserId is already set
      await testApiHandler({
          appHandler: cardApiHandlerModule, 
          params: { cardId: MOCK_INVALID_CARD_ID },
          test: async ({ fetch }) => {
              const res = await fetch({ method: 'DELETE' });
              const json = await res.json();
              expect(res.status).toBe(400);
              expect(json.error).toBe('Invalid card ID format');
          }
      });
    });

    it('should call deleteCardLogic and return its success response', async () => {
      // mockGetCurrentUserId is already set
      const serviceResult = { success: true, data: { id: MOCK_CARD_ID, message: 'Card deleted' }, status: 200 };
      mockDeleteCardLogic.mockResolvedValue(serviceResult);

      await testApiHandler({
        appHandler: cardApiHandlerModule, 
        params: { cardId: MOCK_CARD_ID },
        test: async ({ fetch }) => {
          const res = await fetch({ method: 'DELETE' });
          expect(mockDeleteCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, prismaMock);
          expect(res.status).toBe(200);
          const json = await res.json(); 
          expect(json.message).toBe('Card deleted successfully');
        },
      });
    });

    it('should call deleteCardLogic and return its error response (e.g. 404 card not found by service)', async () => {
      // mockGetCurrentUserId is already set
      const serviceResult = { success: false, error: 'Card not found by service for delete', status: 404 };
      mockDeleteCardLogic.mockResolvedValue(serviceResult);
      await testApiHandler({
          appHandler: cardApiHandlerModule, 
          params: { cardId: MOCK_CARD_ID },
          test: async ({fetch}) => {
              const res = await fetch({ method: 'DELETE' });
              const json = await res.json();
              expect(res.status).toBe(404);
              expect(json.error).toBe('Card not found by service for delete');
          }
      });
    });
  });
}); 