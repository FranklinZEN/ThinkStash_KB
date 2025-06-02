/**
 * @vitest-environment node
 */
/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { POST } from '@/app/api/ai/generate-title/route'; // Assuming this is the correct path
import { NextRequest } from 'next/server';

// --- Reusable Mocks (adapted from rewrite-content.test.ts) ---

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
};

// Placeholder types (adapt as needed or import from actual types)
interface MockContentBlock {
  block_id: string;
  type: 'text' | 'image';
  text_content?: string;
}

// --- Test Suite ---

describe('/api/ai/generate-title POST', () => {
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
    const requestBody = { content_blocks: [{ block_id: '1', type: 'text', text_content: 'Some text' }] as MockContentBlock[] };
    const request = new NextRequest('http://localhost/api/ai/generate-title', {
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
    const request = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify({}), // Missing content_blocks
    });
    const response = await POST(request);
    const responseBodyJson = await response.json();
    expect(response.status).toBe(400);
    expect(responseBodyJson.error).toContain('content_blocks is required');
  });

  it('should return 400 if content_blocks is not an array', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: 'test-user-id' } });
    const request = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: 'not-an-array' }),
    });
    const response = await POST(request);
    const responseBodyJson = await response.json();
    expect(response.status).toBe(400);
    expect(responseBodyJson.error).toContain('content_blocks is required and must be an array');
  });

  it('should use fallback AISERVICE_URL if environment variable is not set and call service', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: 'test-user-id' } });
    const originalEnvAiserviceUrl = process.env.AISERVICE_URL;
    delete process.env.AISERVICE_URL;

    const mockRequestBody = { content_blocks: [{ block_id: '1', type: 'text', text_content: 'Test content' }] as MockContentBlock[] };
    const mockPythonResponse = { suggested_title: 'Fallback Test Title' }; 

    (global.fetch as import('vitest').Mock).mockResolvedValueOnce({
      ok: true, status: 200, json: async () => mockPythonResponse,
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    const request = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify(mockRequestBody),
    });
    await POST(request);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const fetchCallArgs = (global.fetch as import('vitest').Mock).mock.calls[0];
    expect(fetchCallArgs[0]).toBe('http://localhost:8000/generate-title'); 

    process.env.AISERVICE_URL = originalEnvAiserviceUrl;
  });

  it('should successfully call the AI service and return a suggested title', async () => {
    const mockUserId = 'test-user-title-123';
    mockGetServerSession.mockResolvedValue({ user: { id: mockUserId } });

    const requestBody = { content_blocks: [{ block_id: '1', type: 'text', text_content: 'This is a test.' }] as MockContentBlock[] };
    const expectedPythonResponse = { suggested_title: 'A Great Test Title' }; // Python returns this
    
    (global.fetch as import('vitest').Mock).mockResolvedValue({
      ok: true, status: 200, json: async () => expectedPythonResponse,
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    const request = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });

    const response = await POST(request);
    const responseBodyJson = await response.json();

    expect(response.status).toBe(200);
    // The route reshapes the response slightly to GenerateTitleResponse format
    expect(responseBodyJson).toEqual({
        suggested_title: expectedPythonResponse.suggested_title,
        error_message: undefined, // Or null, depending on how Python service sends it if absent
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const fetchCallArgs = (global.fetch as import('vitest').Mock).mock.calls[0];
    expect(fetchCallArgs[0]).toBe(`${mockEnv.AISERVICE_URL}/generate-title`);
    
    const fetchOptions = fetchCallArgs[1] as RequestInit;
    expect(fetchOptions.method).toBe('POST');
    expect(fetchOptions.headers).toEqual({ 'Content-Type': 'application/json' });
    
    const sentPythonPayload = JSON.parse(fetchOptions.body as string);
    expect(sentPythonPayload).toEqual({
      content_blocks: requestBody.content_blocks,
      user_id: mockUserId,
    });
  });

  it('should handle errors from the AI service gracefully', async () => {
    const mockUserId = 'test-user-title-error';
    mockGetServerSession.mockResolvedValue({ user: { id: mockUserId } });

    const requestBody = { content_blocks: [{ block_id: '1', type: 'text', text_content: 'Error content' }] as MockContentBlock[] };
    const mockPythonError = { message: 'AI service title generation failed' }; 

    (global.fetch as import('vitest').Mock).mockResolvedValue({
      ok: false, status: 500, json: async () => mockPythonError,
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    const request = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });

    const response = await POST(request);
    const responseBodyJson = await response.json();

    expect(response.status).toBe(500);
    expect(responseBodyJson).toEqual({
      error: 'Python aiservice failed to generate title.',
      details: mockPythonError.message,
    });
  });

  it('should handle network errors when calling the AI service', async () => {
    const mockUserId = 'test-user-title-network-error';
    mockGetServerSession.mockResolvedValue({ user: { id: mockUserId } });

    const requestBody = { content_blocks: [{ block_id: '1', type: 'text', text_content: 'Some content' }] as MockContentBlock[] };
    const networkError = new TypeError('fetch failed: Title service connection failed'); 

    (global.fetch as import('vitest').Mock).mockRejectedValue(networkError);

    const request = new NextRequest('http://localhost/api/ai/generate-title', {
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