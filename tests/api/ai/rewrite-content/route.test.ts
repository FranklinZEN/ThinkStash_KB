/**
 * @vitest-environment node
 */
/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { POST } from '@/app/api/ai/rewrite-content/route'; // Assuming this is the correct path
import { NextRequest } from 'next/server';
// import { NextResponse } from 'next/server'; // Will be used by the route, not directly in test usually

// --- Reusable Mocks (adapted from reconstruct-and-analyze.test.ts) ---

// Mock next/headers
const mockHeadersInstance = new Headers({ 'x-test-header': 'test' });
const mockHeadersFn = vi.fn(() => mockHeadersInstance);
const mockCookiesGetFn = vi.fn();
const mockCookiesHasFn = vi.fn();
const mockCookiesSetFn = vi.fn();
const mockCookiesDeleteFn = vi.fn();
const mockCookiesGetAllFn = vi.fn(() => []);
const mockCookiesClearFn = vi.fn();
const mockCookiesIteratorFn = vi.fn(function*() {});
const mockCookiesObject = {
  get: mockCookiesGetFn,
  has: mockCookiesHasFn,
  set: mockCookiesSetFn,
  delete: mockCookiesDeleteFn,
  getAll: mockCookiesGetAllFn,
  clear: mockCookiesClearFn,
  [Symbol.iterator]: mockCookiesIteratorFn,
};
const mockCookiesFn = vi.fn(() => mockCookiesObject);

vi.mock('next/headers', () => ({
  __esModule: true,
  headers: mockHeadersFn,
  cookies: mockCookiesFn,
}));

// Mock next-auth/next
const { mockGetServerSession } = vi.hoisted(() => {
  return { mockGetServerSession: vi.fn() };
});
vi.mock('next-auth/next', () => ({
  __esModule: true,
  getServerSession: mockGetServerSession,
}));

// Mock @/lib/auth
vi.mock('@/lib/auth', () => ({
  authOptions: {}, // Provide the expected structure for authOptions
}));

// Mock environment variables - adjust if AISERVICE_URL is different or more specific for this route
const mockEnv = {
  AISERVICE_URL: 'http://mock-aiservice-url.com', // Assuming same base URL for AI services
  // Add other relevant env vars if the route uses them
};

// Placeholder types for request/response payloads (mirror actual types as needed)
// Actual types should be imported from '@/types/api/ai-service' if possible
interface MockContentBlock {
  block_id: string;
  type: 'text' | 'image';
  text_content?: string;
  image_url?: string;
  // add other properties as per your ContentBlock definition
}

interface MockDocumentMetadata {
  original_title?: string;
  source_url?: string;
  // add other properties as per your DocumentMetadata definition
}

// --- Test Suite ---

describe('/api/ai/rewrite-content POST', () => {
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    mockGetServerSession.mockReset();
    mockHeadersFn.mockClear();
    mockHeadersFn.mockReturnValue(new Headers({ 'x-test-header': 'test' }));
    mockCookiesFn.mockClear();
    mockCookiesFn.mockReturnValue(mockCookiesObject);
    mockCookiesGetFn.mockClear();
    mockCookiesHasFn.mockClear();
    mockCookiesSetFn.mockClear();
    mockCookiesDeleteFn.mockClear();
    mockCookiesGetAllFn.mockClear();
    mockCookiesClearFn.mockClear();
    mockCookiesIteratorFn.mockClear();

    vi.stubGlobal('process', { env: { ...process.env, ...mockEnv } });
    originalFetch = global.fetch;
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllGlobals();
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetServerSession.mockResolvedValue(null);
    const requestBody = {
      content_blocks_to_rewrite: [{ block_id: '1', type: 'text', text_content: 'Hello' }] as MockContentBlock[],
    };
    const request = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });
    const response = await POST(request);
    const responseBodyJson = await response.json();
    expect(response.status).toBe(401);
    expect(responseBodyJson).toEqual({ error: 'Unauthorized' });
  });

  it('should return 400 if content_blocks_to_rewrite is missing', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: 'test-user-id' } });
    const request = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify({ document_metadata: {} }), // Missing content_blocks_to_rewrite
    });
    const response = await POST(request);
    const responseBodyJson = await response.json();
    expect(response.status).toBe(400);
    expect(responseBodyJson.error).toContain('content_blocks_to_rewrite is required');
  });

  it('should return 400 if content_blocks_to_rewrite is not an array', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: 'test-user-id' } });
    const request = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify({ content_blocks_to_rewrite: 'not-an-array' }),
    });
    const response = await POST(request);
    const responseBodyJson = await response.json();
    expect(response.status).toBe(400);
    expect(responseBodyJson.error).toContain('content_blocks_to_rewrite is required and must be an array');
  });

  // Test for AISERVICE_URL configuration (similar to reconstruct-and-analyze)
  // Given the route's fallback, this tests if the fallback is used when env var is deleted.
  it('should use fallback AISERVICE_URL if environment variable is not set and call service', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: 'test-user-id' } });
    const originalEnvAiserviceUrl = process.env.AISERVICE_URL;
    delete process.env.AISERVICE_URL; // Delete the env var

    const mockRequestBody = {
      content_blocks_to_rewrite: [{ block_id: '1', type: 'text', text_content: 'Test content' }] as MockContentBlock[],
      document_metadata: { original_title: 'Test Doc' } as MockDocumentMetadata,
    };
    const mockPythonResponse = { 
      ai_rewritten_content_blocks: [{ block_id: 'rewritten-1', type: 'text', text_content: 'Rewritten hello' }] as MockContentBlock[],
      usage_metadata: { tokens: 100, cost: 0.01 },
    }; 

    (global.fetch as import('vitest').Mock).mockResolvedValueOnce({
      ok: true, status: 200, json: async () => mockPythonResponse,
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    const request = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify(mockRequestBody),
    });
    await POST(request); // Call the handler

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const fetchCallArgs = (global.fetch as import('vitest').Mock).mock.calls[0];
    // Expect it to be called with the fallback URL from the route
    expect(fetchCallArgs[0]).toBe(`http://localhost:8000/rewrite-content`); 

    process.env.AISERVICE_URL = originalEnvAiserviceUrl; // Restore
  });

  it('should successfully call the AI service and return rewritten content', async () => {
    const mockUserId = 'test-user-rewrite-123';
    mockGetServerSession.mockResolvedValue({ user: { id: mockUserId } });

    const requestBody = {
      content_blocks_to_rewrite: [{ block_id: '1', type: 'text', text_content: 'Hello world' }] as MockContentBlock[],
      document_metadata: { original_title: 'Test Title' } as MockDocumentMetadata,
      // user_id: mockUserId, // Can be sent, but route prioritizes session user_id
    };
    const expectedPythonResponse = { 
      ai_rewritten_content_blocks: [{ block_id: 'rewritten-1', type: 'text', text_content: 'Rewritten hello world' }] as MockContentBlock[],
      usage_metadata: { tokens: 120, cost: 0.012 },
      // Potentially other fields like error_message: null
    };

    (global.fetch as import('vitest').Mock).mockResolvedValue({
      ok: true, status: 200, json: async () => expectedPythonResponse,
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    const request = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });

    const response = await POST(request);
    const responseBodyJson = await response.json();

    expect(response.status).toBe(200);
    expect(responseBodyJson).toEqual(expectedPythonResponse); // Route directly returns Python response

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const fetchCallArgs = (global.fetch as import('vitest').Mock).mock.calls[0];
    expect(fetchCallArgs[0]).toBe(`${mockEnv.AISERVICE_URL}/rewrite-content`);
    
    const fetchOptions = fetchCallArgs[1] as RequestInit;
    expect(fetchOptions.method).toBe('POST');
    expect(fetchOptions.headers).toEqual({ 'Content-Type': 'application/json' });
    
    const sentPythonPayload = JSON.parse(fetchOptions.body as string);
    expect(sentPythonPayload).toEqual({
      content_blocks_to_rewrite: requestBody.content_blocks_to_rewrite,
      document_metadata: requestBody.document_metadata,
      user_id: mockUserId, // Route ensures session user_id is used
    });
  });

  it('should handle errors from the AI service gracefully (e.g., AI service returns 500)', async () => {
    const mockUserId = 'test-user-rewrite-error';
    mockGetServerSession.mockResolvedValue({ user: { id: mockUserId } });

    const requestBody = {
      content_blocks_to_rewrite: [{ block_id: '1', type: 'text', text_content: 'Content causing error' }] as MockContentBlock[],
    };
    const mockPythonError = { message: 'AI service internal rewrite error' }; 

    (global.fetch as import('vitest').Mock).mockResolvedValue({
      ok: false, status: 500, json: async () => mockPythonError,
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    const request = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });

    const response = await POST(request);
    const responseBodyJson = await response.json();

    expect(response.status).toBe(500);
    expect(responseBodyJson).toEqual({
      error: 'Python aiservice failed to rewrite content.',
      details: mockPythonError.message,
    });
  });

  it('should handle network errors when calling the AI service (fetch throws an error)', async () => {
    const mockUserId = 'test-user-rewrite-network-error';
    mockGetServerSession.mockResolvedValue({ user: { id: mockUserId } });

    const requestBody = {
      content_blocks_to_rewrite: [{ block_id: '1', type: 'text', text_content: 'Some content' }] as MockContentBlock[],
    };
    const networkError = new TypeError('fetch failed: Rewrite service connection failed'); 

    (global.fetch as import('vitest').Mock).mockRejectedValue(networkError);

    const request = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });

    const response = await POST(request);
    const responseBodyJson = await response.json();

    expect(response.status).toBe(503);
    expect(responseBodyJson).toEqual({
      error: 'Failed to connect to Python aiservice.',
      details: networkError.message,
    });
  });
}); 