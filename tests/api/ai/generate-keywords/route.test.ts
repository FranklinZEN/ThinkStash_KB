/**
 * @vitest-environment node
 */
/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { POST } from '@/app/api/ai/generate-keywords/route'; // Assuming this is the correct path
import { NextRequest } from 'next/server';

// --- Reusable Mocks (adapted from generate-title.test.ts) ---

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
  authOptions: {}, 
}));

// Mock environment variables
const mockEnv = {
  AISERVICE_URL: 'http://mock-aiservice-url.com',
  // Add other relevant env vars if the route uses them
};

// Placeholder types for request/response payloads (adapt as needed)
// Actual types should be imported from '@/types/api/ai-service' if possible
interface MockContentBlock {
  block_id: string;
  type: 'text' | 'image'; // Assuming content blocks can be text or image
  text_content?: string;
  // image_url?: string; // If images can be part of content for keyword gen
}

interface MockGenerateKeywordsRequest {
  content_blocks: MockContentBlock[];
  existing_keywords?: string[];
  // add other properties as per your GenerateKeywordsRequest definition
}

interface MockGenerateKeywordsResponse {
  suggested_keywords?: string[];
  error_message?: string;
  // add other properties as per your GenerateKeywordsResponse definition
}

// --- Test Suite ---

describe('/api/ai/generate-keywords POST', () => {
  let originalFetch: typeof global.fetch;
  // Store original process.env to restore it
  let originalProcessEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    // Save original process.env
    originalProcessEnv = { ...process.env };

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

    // Stub process.env for this test suite
    vi.stubGlobal('process', { env: { ...originalProcessEnv, ...mockEnv } });
    originalFetch = global.fetch;
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    // Restore original process.env
    process.env = originalProcessEnv;
    vi.unstubAllGlobals(); 
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetServerSession.mockResolvedValue(null);
    const requestBody: MockGenerateKeywordsRequest = { content_blocks: [{ block_id: '1', type: 'text', text_content: 'Some text' }] };
    const request = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });
    const response = await POST(request);
    const responseBodyJson = await response.json();
    expect(response.status).toBe(401);
    expect(responseBodyJson).toEqual({ error: 'Unauthorized' });
  });

  it('should return 400 if content_blocks is missing', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: 'test-user-id' } });
    const request = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({}), // Missing content_blocks
    });
    const response = await POST(request);
    const responseBodyJson = await response.json();
    expect(response.status).toBe(400);
    expect(responseBodyJson.error).toContain('content_blocks is required and must be an array');
  });

  it('should return 400 if content_blocks is not an array', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: 'test-user-id' } });
    const request = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: 'not-an-array' }),
    });
    const response = await POST(request);
    const responseBodyJson = await response.json();
    expect(response.status).toBe(400);
    expect(responseBodyJson.error).toContain('content_blocks is required and must be an array');
  });

  it('should use fallback AISERVICE_URL if environment variable is not set and call service successfully', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: 'test-user-id' } });
    
    // Temporarily delete AISERVICE_URL from the mocked process.env for this test
    const originalMockEnvAiserviceUrl = mockEnv.AISERVICE_URL;
    const tempEnv = { ...process.env }; // Create a mutable copy
    delete tempEnv.AISERVICE_URL;
    vi.stubGlobal('process', { env: tempEnv });

    const mockRequestBody: MockGenerateKeywordsRequest = { content_blocks: [{ block_id: '1', type: 'text', text_content: 'Test content' }] };
    const mockPythonResponse = { suggested_keywords: ['fallback', 'test', 'keywords'] }; 

    (global.fetch as import('vitest').Mock).mockResolvedValueOnce({
      ok: true, status: 200, json: async () => mockPythonResponse,
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    const request = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify(mockRequestBody),
    });
    await POST(request);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const fetchCallArgs = (global.fetch as import('vitest').Mock).mock.calls[0];
    expect(fetchCallArgs[0]).toBe('http://localhost:8000/generate-keywords'); 

    // Restore AISERVICE_URL in mockEnv for other tests
    vi.stubGlobal('process', { env: { ...process.env, AISERVICE_URL: originalMockEnvAiserviceUrl } });
  });

  it('should successfully call the AI service and return suggested keywords', async () => {
    const mockUserId = 'test-user-keywords-123';
    mockGetServerSession.mockResolvedValue({ user: { id: mockUserId } });

    const requestBody: MockGenerateKeywordsRequest = { content_blocks: [{ block_id: '1', type: 'text', text_content: 'This is a test for keywords.' }], existing_keywords: ['initial'] };
    const expectedPythonResponse = { suggested_keywords: ['test', 'keywords', 'generation'] }; // Python returns this
    
    (global.fetch as import('vitest').Mock).mockResolvedValue({
      ok: true, status: 200, json: async () => expectedPythonResponse,
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    const request = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });

    const response = await POST(request);
    const responseBodyJson = await response.json();

    expect(response.status).toBe(200);
    expect(responseBodyJson).toEqual({
        suggested_keywords: expectedPythonResponse.suggested_keywords,
        error_message: undefined, 
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const fetchCallArgs = (global.fetch as import('vitest').Mock).mock.calls[0];
    expect(fetchCallArgs[0]).toBe(`${mockEnv.AISERVICE_URL}/generate-keywords`);
    
    const fetchOptions = fetchCallArgs[1] as RequestInit;
    expect(fetchOptions.method).toBe('POST');
    expect(fetchOptions.headers).toEqual({ 'Content-Type': 'application/json' });
    
    const sentPythonPayload = JSON.parse(fetchOptions.body as string);
    // The route only sends content_blocks and user_id, not existing_keywords to the python service
    expect(sentPythonPayload).toEqual({
      content_blocks: requestBody.content_blocks,
      user_id: mockUserId,
    });
  });

  it('should handle errors from the AI service gracefully', async () => {
    const mockUserId = 'test-user-keywords-error';
    mockGetServerSession.mockResolvedValue({ user: { id: mockUserId } });

    const requestBody: MockGenerateKeywordsRequest = { content_blocks: [{ block_id: '1', type: 'text', text_content: 'Error content for keywords' }] };
    const mockPythonError = { message: 'AI service keyword generation failed' }; 

    (global.fetch as import('vitest').Mock).mockResolvedValue({
      ok: false, status: 500, json: async () => mockPythonError,
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    const request = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });

    const response = await POST(request);
    const responseBodyJson = await response.json();

    expect(response.status).toBe(500);
    expect(responseBodyJson).toEqual({
      error: 'Python aiservice failed to generate keywords.',
      details: mockPythonError.message,
    });
  });

  it('should handle network errors when calling the AI service', async () => {
    const mockUserId = 'test-user-keywords-network-error';
    mockGetServerSession.mockResolvedValue({ user: { id: mockUserId } });

    const requestBody: MockGenerateKeywordsRequest = { content_blocks: [{ block_id: '1', type: 'text', text_content: 'Some content for keywords' }] };
    const networkError = new TypeError('fetch failed: Keyword service connection failed'); 

    (global.fetch as import('vitest').Mock).mockRejectedValue(networkError);

    const request = new NextRequest('http://localhost/api/ai/generate-keywords', {
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