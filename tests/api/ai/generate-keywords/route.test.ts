/**
 * @vitest-environment node
 */
/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { POST } from '@/app/api/ai/generate-keywords/route';
import { NextRequest } from 'next/server';
import {
  GenerateKeywordsRequest,
  GenerateKeywordsResponse,
  ContentBlock,
} from '@/types/api/ai-service';

// Mocks for next/headers and next-auth
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

const { mockGetServerSession } = vi.hoisted(() => {
  return { mockGetServerSession: vi.fn() };
});

vi.mock('next-auth/next', () => ({
  __esModule: true,
  getServerSession: mockGetServerSession,
}));

vi.mock('@/lib/auth', () => ({
  authOptions: {},
}));

const baseMockEnv = {};

describe('/api/ai/generate-keywords POST', () => {
  let originalFetch: typeof global.fetch;
  let originalProcessEnv: NodeJS.ProcessEnv;

  const mockUserId = 'test-user-keyword-gen';
  const sampleContentBlocks: ContentBlock[] = [
    { block_id: 'cb1', type: 'text', text_content: 'This is a sample text about AI and machine learning.' },
    { block_id: 'cb2', type: 'text', text_content: 'It explores various concepts and applications.' },
  ];

  beforeEach(() => {
    originalProcessEnv = { ...process.env };
    vi.stubGlobal('process', { env: { ...originalProcessEnv, ...baseMockEnv } });

    mockGetServerSession.mockReset();
    mockHeadersFn.mockClear().mockReturnValue(new Headers({ 'x-test-header': 'test' }));
    mockCookiesFn.mockClear().mockReturnValue(mockCookiesObject);
    mockCookiesGetFn.mockClear();
    mockCookiesHasFn.mockClear();
    mockCookiesSetFn.mockClear();
    mockCookiesDeleteFn.mockClear();
    mockCookiesGetAllFn.mockClear().mockReturnValue([]);
    mockCookiesClearFn.mockClear();
    (mockCookiesIteratorFn as Mock).mockClear();

    originalFetch = global.fetch;
    global.fetch = vi.fn();

    mockGetServerSession.mockResolvedValue({
      user: { id: mockUserId, email: 'test@example.com' },
      expires: 'some-future-date',
    });
    process.env.AISERVICE_URL = 'http://mock-aiservice-url.com';
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllGlobals();
    process.env = originalProcessEnv;
  });

  it('should successfully generate keywords and return them', async () => {
    const mockSuggestedKeywords = ['AI', 'machine learning', 'concepts', 'applications'];
    const mockPythonResponse = { suggested_keywords: mockSuggestedKeywords };

    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponse,
      status: 200,
    } as Response);

    const requestBody: GenerateKeywordsRequest = { content_blocks: sampleContentBlocks };
    const req = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });

    const response = await POST(req);
    const responseBody = (await response.json()) as GenerateKeywordsResponse;

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      `${process.env.AISERVICE_URL}/generate-keywords`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.any(String),
      })
    );
    const fetchCallArgs = (global.fetch as Mock).mock.calls[0];
    const fetchBody = JSON.parse(fetchCallArgs[1].body as string);
    expect(fetchBody).toEqual({ content_blocks: sampleContentBlocks }); // user_id is not sent

    expect(responseBody.suggested_keywords).toEqual(mockSuggestedKeywords);
    expect(responseBody.error_message).toBeUndefined();
  });

  it('should handle Python service returning empty suggested_keywords on 200 OK', async () => {
    const mockPythonResponse = { suggested_keywords: [] };
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true, json: async () => mockPythonResponse, status: 200
    } as Response);
    const req = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = (await response.json()) as GenerateKeywordsResponse;
    expect(response.status).toBe(200);
    expect(responseBody.suggested_keywords).toEqual([]);
    expect(responseBody.error_message).toBeUndefined();
  });
  
  it('should handle Python service returning null for suggested_keywords on 200 OK', async () => {
    const mockPythonResponse = { suggested_keywords: null }; // Python might send null
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true, json: async () => mockPythonResponse, status: 200
    } as Response);
     const req = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = (await response.json()) as GenerateKeywordsResponse;
    expect(response.status).toBe(200);
    expect(responseBody.suggested_keywords).toEqual([]); // Route should default to empty array
    expect(responseBody.error_message).toBeUndefined();
  });
  
  it('should handle Python service returning a response without suggested_keywords field on 200 OK', async () => {
    const mockPythonResponse = {}; // suggested_keywords field is missing
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true, json: async () => mockPythonResponse, status: 200
    } as Response);
     const req = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = (await response.json()) as GenerateKeywordsResponse;
    expect(response.status).toBe(200);
    expect(responseBody.suggested_keywords).toEqual([]); // Route should default to empty array
    expect(responseBody.error_message).toBeUndefined();
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetServerSession.mockResolvedValue(null);
    const req = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(401);
    expect(responseBody).toEqual({ error: 'Unauthorized' });
  });

  it('should return 400 if content_blocks is missing', async () => {
    const req = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({}), // Missing content_blocks
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(400);
    expect(responseBody.error).toBe('Invalid request body: content_blocks is required and must be an array.');
  });

  it('should return 400 if content_blocks is not an array', async () => {
    const req = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: 'not-an-array' }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(400);
    expect(responseBody.error).toBe('Invalid request body: content_blocks is required and must be an array.');
  });

  it('should use fallback AISERVICE_URL if environment variable is not set', async () => {
    const fallbackAIServiceURL = 'http://localhost:8000';
    delete process.env.AISERVICE_URL;
    (global.fetch as Mock).mockResolvedValueOnce({ ok: true, json: async () => ({ suggested_keywords: ['fallback'] }) } as Response);
    const req = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    await POST(req);
    expect(global.fetch).toHaveBeenCalledWith(`${fallbackAIServiceURL}/generate-keywords`, expect.any(Object));
  });

  it('should handle Python service error (JSON response from Python)', async () => {
    const pythonError = { message: 'Python keyword gen failed' };
    (global.fetch as Mock).mockResolvedValueOnce({ ok: false, status: 500, json: async () => pythonError } as Response);
    const req = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(500);
    expect(responseBody.error).toBe('Python aiservice failed to generate keywords.');
    expect(responseBody.details).toBe(pythonError.message);
  });

  it('should handle Python service error (non-JSON response from Python)', async () => {
    const pythonErrorText = 'Python service unavailable for keyword generation';
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: false, status: 502, text: async () => pythonErrorText, json: async () => { throw new Error('not json'); },
      headers: new Headers(), redirected: false, type: 'basic', url: 'mockurl',
      clone: vi.fn(), arrayBuffer: vi.fn(), blob: vi.fn(), formData: vi.fn(), body: null, bodyUsed: false,
    } as unknown as Response);
    const req = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(502);
    expect(responseBody.error).toBe('Python aiservice failed to generate keywords.');
    expect(responseBody.details).toBe(pythonErrorText);
  });

  it('should handle network error when fetching from Python service', async () => {
    (global.fetch as Mock).mockRejectedValueOnce(new TypeError('fetch failed for keywords')); // Message includes 'fetch failed'
    const req = new NextRequest('http://localhost/api/ai/generate-keywords', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(503);
    expect(responseBody.error).toBe('Failed to connect to Python aiservice.');
    expect(responseBody.details).toBe('fetch failed for keywords');
  });
}); 