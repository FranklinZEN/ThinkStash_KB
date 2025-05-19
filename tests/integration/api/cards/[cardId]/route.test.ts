/**
 * @jest-environment node
 */
import 'next-test-api-route-handler'; // Must be first
import { testApiHandler } from 'next-test-api-route-handler';
import * as cardApiHandlerModule from '@/app/api/cards/[cardId]/route'; // Reverted to import * as
import { getCurrentUserId } from '@/lib/sessionUtils';
import { getCardLogic, updateCardLogic, deleteCardLogic, UpdateCardData } from '@/lib/services/cardService';

// Mock dependencies
jest.mock('@/lib/sessionUtils', () => ({
  getCurrentUserId: jest.fn(),
}));
jest.mock('@/lib/services/cardService', () => ({
  getCardLogic: jest.fn(),
  updateCardLogic: jest.fn(),
  deleteCardLogic: jest.fn(),
}));

const mockGetCurrentUserId = getCurrentUserId as jest.Mock;
const mockGetCardLogic = getCardLogic as jest.Mock;
const mockUpdateCardLogic = updateCardLogic as jest.Mock;
const mockDeleteCardLogic = deleteCardLogic as jest.Mock;

const MOCK_USER_ID = 'user-card-test-123';
const MOCK_CARD_ID = 'clxkz1g5g000008l4g3z3h2j9'; // Example of a valid CUID (25 chars, starts with 'c')
const MOCK_INVALID_CARD_ID = 'invalid-cuid-format'; // Keep as clearly invalid

const validUpdatePayload: UpdateCardData = {
  title: 'Updated Test Card Title',
  content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Updated content.' }] }],
  folderId: null, // Example: moving to root
  tags: ['updated', 'jest'],
};

describe('GET /api/cards/[cardId]', () => {
  beforeEach(() => {
    mockGetCurrentUserId.mockReset();
    mockGetCardLogic.mockReset();
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetCurrentUserId.mockResolvedValue(null);
    await testApiHandler({
      appHandler: cardApiHandlerModule, // Use the entire module
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
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID);
    await testApiHandler({
      appHandler: cardApiHandlerModule, // Use the entire module
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
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID);
    const serviceResponseData = { id: MOCK_CARD_ID, title: 'Test Card', /* ...other card fields */ };
    const serviceResult = { success: true, data: serviceResponseData, status: 200 };
    mockGetCardLogic.mockResolvedValue(serviceResult);

    await testApiHandler({
      appHandler: cardApiHandlerModule, // Use the entire module
      params: { cardId: MOCK_CARD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        const json = await res.json();
        expect(mockGetCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, expect.anything());
        expect(res.status).toBe(200);
        expect(json).toEqual(serviceResponseData);
      },
    });
  });

  it('should call getCardLogic and return its error response (e.g., 404 not found)', async () => {
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID);
    const serviceResult = { success: false, error: 'Card not found', status: 404 };
    mockGetCardLogic.mockResolvedValue(serviceResult);

    await testApiHandler({
      appHandler: cardApiHandlerModule, // Use the entire module
      params: { cardId: MOCK_CARD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        const json = await res.json();
        expect(mockGetCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, expect.anything());
        expect(res.status).toBe(404);
        expect(json.error).toBe('Card not found');
      },
    });
  });
});

describe('PUT /api/cards/[cardId]', () => {
  beforeEach(() => {
    mockGetCurrentUserId.mockReset();
    mockUpdateCardLogic.mockReset();
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetCurrentUserId.mockResolvedValue(null);
    await testApiHandler({
      appHandler: cardApiHandlerModule, // Use the entire module
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
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID);
    await testApiHandler({
        appHandler: cardApiHandlerModule, // Use the entire module
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
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID);
    await testApiHandler({
      appHandler: cardApiHandlerModule, // Use the entire module
      params: { cardId: MOCK_CARD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'PUT', body: JSON.stringify({ title: '' }) }); // Invalid: empty title
        const json = await res.json();
        expect(res.status).toBe(400);
        expect(json.error).toBe('Validation failed');
        expect(mockUpdateCardLogic).not.toHaveBeenCalled();
      },
    });
  });

  it('should call updateCardLogic and return its success response', async () => {
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID);
    const serviceResponseData = { id: MOCK_CARD_ID, ...validUpdatePayload };
    const serviceResult = { success: true, data: serviceResponseData, status: 200 };
    mockUpdateCardLogic.mockResolvedValue(serviceResult);

    await testApiHandler({
      appHandler: cardApiHandlerModule, // Use the entire module
      params: { cardId: MOCK_CARD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'PUT', body: JSON.stringify(validUpdatePayload) });
        const json = await res.json();
        expect(mockUpdateCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, validUpdatePayload, expect.anything());
        expect(res.status).toBe(200);
        expect(json).toEqual(serviceResponseData);
      },
    });
  });

  it('should call updateCardLogic and return its error response (e.g. 404 card not found by service)', async () => {
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID);
    const serviceResult = { success: false, error: 'Card not found by service', status: 404 };
    mockUpdateCardLogic.mockResolvedValue(serviceResult);
    await testApiHandler({
        appHandler: cardApiHandlerModule, // Use the entire module
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
  beforeEach(() => {
    mockGetCurrentUserId.mockReset();
    mockDeleteCardLogic.mockReset();
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetCurrentUserId.mockResolvedValue(null);
    await testApiHandler({
      appHandler: cardApiHandlerModule, // Use the entire module
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
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID);
    await testApiHandler({
        appHandler: cardApiHandlerModule, // Use the entire module
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
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID);
    const serviceResult = { success: true, data: { id: MOCK_CARD_ID, message: 'Card deleted' }, status: 200 };
    mockDeleteCardLogic.mockResolvedValue(serviceResult);

    await testApiHandler({
      appHandler: cardApiHandlerModule, // Use the entire module
      params: { cardId: MOCK_CARD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'DELETE' });
        // For DELETE, often the body is empty or a simple message, check status primarily
        expect(mockDeleteCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, expect.anything());
        expect(res.status).toBe(200);
        // Check body if your route returns one, e.g. { message: ... }
        const json = await res.json(); 
        expect(json.message).toBe('Card deleted successfully'); // As per current route handler
      },
    });
  });

  it('should call deleteCardLogic and return its error response (e.g. 404 card not found by service)', async () => {
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID);
    const serviceResult = { success: false, error: 'Card not found by service for delete', status: 404 };
    mockDeleteCardLogic.mockResolvedValue(serviceResult);
    await testApiHandler({
        appHandler: cardApiHandlerModule, // Use the entire module
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