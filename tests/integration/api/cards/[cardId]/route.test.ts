/**
 * @jest-environment node
 */
import { GET, PUT, DELETE } from '@/app/api/cards/[cardId]/route'; 
import { UpdateCardData } from '@/lib/services/cardService'; 
import { prismaMock } from 'tests/__helpers__/prisma-mock'; 
import { mockGetCurrentUserId } from 'tests/vitest.setup'; 
import { 
  mockGetCardLogic,
  mockUpdateCardLogic,
  mockDeleteCardLogic,
} from 'tests/__helpers__/card-service-mock'; 
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createMocks, RequestMethod } from 'node-mocks-http';
import { NextRequest } from 'next/server';

const MOCK_USER_ID = 'user-card-test-123';
const MOCK_CARD_ID = 'clxkz1g5g000008l4g3z3h2j9'; 
const MOCK_INVALID_CARD_ID = 'invalid-cuid-format'; 

const validUpdatePayload: UpdateCardData = {
  title: 'Updated Test Card Title',
  content: [{
    id: 'block-id-for-test',
    type: 'paragraph', 
    content: [{ type: 'text', text: 'Updated content.' }] 
  }],
  folderId: null, 
  tags: ['updated', 'vitest'],
};

// Helper to create a mock NextRequest and context for dynamic routes
// Define the specific context structure the API handlers expect
interface CardIdRouteContext {
  params: Promise<{ cardId: string }>;
}

function mockRequestAndContext(
  method: RequestMethod,
  routeParams: { cardId: string }, // routeParams must now contain cardId
  body?: any,
) {
  const cardIdParam = routeParams.cardId; // No need for default if always present
  const url = `/api/cards/${cardIdParam}`;

  const { req } = createMocks({
    method,
    url,
    body: body ? JSON.stringify(body) : undefined,
    headers: body ? { 'Content-Type': 'application/json' } : {},
  });

  const nextReq = req as unknown as NextRequest & { json: () => Promise<any> };
  nextReq.json = async () => (body ? JSON.parse(JSON.stringify(body)) : Promise.resolve(undefined));
  
  (nextReq as any).nextUrl = {
    searchParams: new URLSearchParams(), 
    pathname: url, 
  };

  // Create the context object with the params wrapped in a Promise
  const context: CardIdRouteContext = { params: Promise.resolve(routeParams) }; 
  return { req: nextReq, context };
}

describe('/api/cards/[cardId] API Route Handlers', () => {
  beforeEach(() => {
    vi.resetAllMocks(); // Use Vitest's resetAllMocks
    mockGetCurrentUserId.mockResolvedValue(MOCK_USER_ID); 
    
    // Service mocks are reset by vi.resetAllMocks() as they are vi.fn()
    // prismaMock reset is handled by its own beforeEach in vitest.setup.ts
  });

  describe('GET handler', () => {
    it('should return 401 if user is not authenticated', async () => {
      mockGetCurrentUserId.mockReset().mockResolvedValue(null);
      const { req, context } = mockRequestAndContext('GET', { cardId: MOCK_CARD_ID });
      const response = await GET(req, context);
      const json = await response.json();
      expect(response.status).toBe(401);
      expect(json.error).toBe('Unauthorized');
      expect(mockGetCardLogic).not.toHaveBeenCalled();
    });

    it('should return 400 for invalid card ID format', async () => {
      const { req, context } = mockRequestAndContext('GET', { cardId: MOCK_INVALID_CARD_ID });
      const response = await GET(req, context);
      const json = await response.json();
      expect(response.status).toBe(400);
      expect(json.error).toBe('Invalid card ID format'); 
      expect(mockGetCardLogic).not.toHaveBeenCalled();
    });

    it('should call getCardLogic and return its success response', async () => {
      const serviceResponseData = { id: MOCK_CARD_ID, title: 'Test Card' };
      const serviceResult = { success: true, data: serviceResponseData, status: 200 };
      mockGetCardLogic.mockResolvedValue(serviceResult);
      const { req, context } = mockRequestAndContext('GET', { cardId: MOCK_CARD_ID });
      const response = await GET(req, context);
      const json = await response.json();
      expect(mockGetCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, prismaMock);
      expect(response.status).toBe(200);
      expect(json).toEqual(serviceResponseData);
    });

    it('should call getCardLogic and return its error response (e.g., 404 not found)', async () => {
      const serviceResult = { success: false, error: 'Card not found', status: 404 };
      mockGetCardLogic.mockResolvedValue(serviceResult);
      const { req, context } = mockRequestAndContext('GET', { cardId: MOCK_CARD_ID });
      const response = await GET(req, context);
      const json = await response.json();
      expect(mockGetCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, prismaMock);
      expect(response.status).toBe(404);
      expect(json.error).toBe('Card not found');
    });
  });

  describe('PUT handler', () => {
    it('should return 401 if user is not authenticated', async () => {
      mockGetCurrentUserId.mockReset().mockResolvedValue(null);
      const { req, context } = mockRequestAndContext('PUT', { cardId: MOCK_CARD_ID }, validUpdatePayload);
      const response = await PUT(req, context);
      const json = await response.json();
      expect(response.status).toBe(401);
      expect(json.error).toBe('Unauthorized');
      expect(mockUpdateCardLogic).not.toHaveBeenCalled();
    });
    
    it('should return 400 for invalid card ID format', async () => {
      const { req, context } = mockRequestAndContext('PUT', { cardId: MOCK_INVALID_CARD_ID }, validUpdatePayload);
      const response = await PUT(req, context);
      const json = await response.json();
      expect(response.status).toBe(400);
      expect(json.error).toBe('Invalid card ID format');
    });

    it('should return 400 for invalid request body (Zod validation)', async () => {
      const { req, context } = mockRequestAndContext('PUT', { cardId: MOCK_CARD_ID }, { title: '' }); 
      const response = await PUT(req, context);
      const json = await response.json();
      expect(response.status).toBe(400);
      expect(json.error).toBe('Validation failed');
      expect(mockUpdateCardLogic).not.toHaveBeenCalled();
    });

    it('should call updateCardLogic and return its success response', async () => {
      const serviceResponseData = { id: MOCK_CARD_ID, ...validUpdatePayload };
      const serviceResult = { success: true, data: serviceResponseData, status: 200 };
      mockUpdateCardLogic.mockResolvedValue(serviceResult);
      const { req, context } = mockRequestAndContext('PUT', { cardId: MOCK_CARD_ID }, validUpdatePayload);
      const response = await PUT(req, context);
      const json = await response.json();
      expect(mockUpdateCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, validUpdatePayload, prismaMock);
      expect(response.status).toBe(200);
      expect(json).toEqual(serviceResponseData);
    });

    it('should call updateCardLogic and return its error response (e.g. 404 card not found by service)', async () => {
      const serviceResult = { success: false, error: 'Card not found by service', status: 404 };
      mockUpdateCardLogic.mockResolvedValue(serviceResult);
      const { req, context } = mockRequestAndContext('PUT', { cardId: MOCK_CARD_ID }, validUpdatePayload);
      const response = await PUT(req, context);
      const json = await response.json();
      expect(response.status).toBe(404);
      expect(json.error).toBe('Card not found by service');
    });
  });

  describe('DELETE handler', () => {
    it('should return 401 if user is not authenticated', async () => {
      mockGetCurrentUserId.mockReset().mockResolvedValue(null);
      const { req, context } = mockRequestAndContext('DELETE', { cardId: MOCK_CARD_ID });
      const response = await DELETE(req, context);
      const json = await response.json();
      expect(response.status).toBe(401);
      expect(json.error).toBe('Unauthorized');
      expect(mockDeleteCardLogic).not.toHaveBeenCalled();
    });

    it('should return 400 for invalid card ID format', async () => {
      const { req, context } = mockRequestAndContext('DELETE', { cardId: MOCK_INVALID_CARD_ID });
      const response = await DELETE(req, context);
      const json = await response.json();
      expect(response.status).toBe(400);
      expect(json.error).toBe('Invalid card ID format');
    });

    it('should call deleteCardLogic and return its success response', async () => {
      const serviceResult = { success: true, data: { id: MOCK_CARD_ID, message: 'Card deleted' }, status: 200 };
      mockDeleteCardLogic.mockResolvedValue(serviceResult);
      const { req, context } = mockRequestAndContext('DELETE', { cardId: MOCK_CARD_ID });
      const response = await DELETE(req, context);
      expect(mockDeleteCardLogic).toHaveBeenCalledWith(MOCK_CARD_ID, MOCK_USER_ID, prismaMock);
      expect(response.status).toBe(200);
      const json = await response.json(); 
      expect(json.message).toBe('Card deleted successfully');
    });

    it('should call deleteCardLogic and return its error response (e.g. 404 card not found by service)', async () => {
      const serviceResult = { success: false, error: 'Card not found by service for delete', status: 404 };
      mockDeleteCardLogic.mockResolvedValue(serviceResult);
      const { req, context } = mockRequestAndContext('DELETE', { cardId: MOCK_CARD_ID });
      const response = await DELETE(req, context);
      const json = await response.json();
      expect(response.status).toBe(404);
      expect(json.error).toBe('Card not found by service for delete');
    });
  });
}); 