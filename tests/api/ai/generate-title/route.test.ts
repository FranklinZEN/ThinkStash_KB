/**
 * @vitest-environment node
 */
/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { POST } from '@/app/api/ai/generate-title/route';
import { NextRequest } from 'next/server';
import {
  GenerateTitleRequest,
  GenerateTitleResponse,
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

describe('/api/ai/generate-title POST', () => {
  let originalFetch: typeof global.fetch;
  let originalProcessEnv: NodeJS.ProcessEnv;

  const mockUserId = 'test-user-title-gen';
  const mockContentBlocks: ContentBlock[] = [
    { block_id: 'cb1', user_id: 'user1', document_id: 'doc1', type: 'text', content: 'Main topic of the document, covering various aspects.' },
    { block_id: 'cb2', user_id: 'user1', document_id: 'doc1', type: 'text', content: 'Secondary details and elaborations.' },
  ];

  const mockEmptyContentBlocks: ContentBlock[] = [
    { block_id: 'cb1', user_id: 'user1', document_id: 'doc1', type: 'text', content: '' },
    { block_id: 'cb2', user_id: 'user1', document_id: 'doc1', type: 'text', content: null },
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

  it('should successfully generate a title and return it', async () => {
    const mockSuggestedTitle = 'A Fascinating Look into AI Content';
    const mockPythonResponse = { suggested_title: mockSuggestedTitle };

    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponse,
      status: 200,
    } as Response);

    const requestBody: GenerateTitleRequest = { content_blocks: mockContentBlocks };
    const req = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });

    const response = await POST(req);
    const responseBody = (await response.json()) as GenerateTitleResponse;

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      `${process.env.AISERVICE_URL}/api/v1/ai/generate-title`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.any(String),
      })
    );
    const fetchCallArgs = (global.fetch as Mock).mock.calls[0];
    const fetchBody = JSON.parse(fetchCallArgs[1].body as string);
    expect(fetchBody).toEqual({
      content_blocks: mockContentBlocks,
      existing_title: undefined,
    });

    expect(responseBody.suggested_title).toBe(mockSuggestedTitle);
    expect(responseBody.error_message).toBeUndefined();
  });

  it('should handle Python service returning an error string in suggested_title', async () => {
    const mockErrorTitle = 'Error: Content too short to generate a meaningful title.';
    const mockPythonResponse = { suggested_title: mockErrorTitle };
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true, json: async () => mockPythonResponse, status: 200
    } as Response);

    const req = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: mockContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = (await response.json()) as GenerateTitleResponse;
    expect(response.status).toBe(200);
    expect(responseBody.suggested_title).toBe('');
    expect(responseBody.error_message).toBe(mockErrorTitle);
  });

  it('should handle Python service returning an unexpected empty/null suggested_title on 200 OK', async () => {
    const mockPythonResponse = { suggested_title: null }; // Or undefined, or empty string
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true, json: async () => mockPythonResponse, status: 200
    } as Response);
    const req = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: mockContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = (await response.json()) as GenerateTitleResponse;
    expect(response.status).toBe(200);
    expect(responseBody.suggested_title).toBe('');
    expect(responseBody.error_message).toBe('Python service returned an unexpected response format for title generation.');
  });


  it('should return 401 if user is not authenticated', async () => {
    mockGetServerSession.mockResolvedValue(null);
    const req = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: mockContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(401);
    expect(responseBody).toEqual({ error: 'Unauthorized' });
  });

  it('should return 400 if content_blocks is missing', async () => {
    const req = new NextRequest('http://localhost/api/ai/generate-title', {
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
    const req = new NextRequest('http://localhost/api/ai/generate-title', {
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
    (global.fetch as Mock).mockResolvedValueOnce({ ok: true, json: async () => ({ suggested_title: 'Fallback Title' }) } as Response);
    const req = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: mockContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    await POST(req);
    expect(global.fetch).toHaveBeenCalledWith(`${fallbackAIServiceURL}/api/v1/ai/generate-title`, expect.any(Object));
  });

  it('should handle Python service error (JSON response from Python)', async () => {
    const pythonError = { message: 'Python title gen failed' };
    (global.fetch as Mock).mockResolvedValueOnce({ ok: false, status: 500, json: async () => pythonError } as Response);
    const req = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: mockContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(500);
    expect(responseBody.error).toBe('Python aiservice failed to generate title.');
    expect(responseBody.details).toBe(pythonError.message);
  });

  it('should handle Python service error (non-JSON response from Python)', async () => {
    const pythonErrorText = 'Python service unavailable for title generation';
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: false, status: 502, text: async () => pythonErrorText, json: async () => { throw new Error(); }, // Ensure .json() fails
      headers: new Headers(), redirected: false, type: 'basic', url: 'mockurl',
      clone: vi.fn(), arrayBuffer: vi.fn(), blob: vi.fn(), formData: vi.fn(), body: null, bodyUsed: false,
    } as unknown as Response);
    const req = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: mockContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(502);
    expect(responseBody.error).toBe('Python aiservice failed to generate title.');
    expect(responseBody.details).toBe(pythonErrorText);
  });

  it('should handle network error when fetching from Python service', async () => {
    (global.fetch as Mock).mockRejectedValueOnce(new TypeError('Network error for title gen'));
    const req = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify({ content_blocks: mockContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(503);
    expect(responseBody.error).toBe('Failed to connect to Python aiservice.');
    expect(responseBody.details).toBe('Network error for title gen');
  });

  it('should handle empty/null content blocks', async () => {
    const mockSuggestedTitle = 'A Fascinating Look into AI Content';
    const mockPythonResponse = { suggested_title: mockSuggestedTitle };

    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponse,
      status: 200,
    } as Response);

    const requestBody: GenerateTitleRequest = {
      content_blocks: mockEmptyContentBlocks,
      existing_title: undefined,
    };
    const req = new NextRequest('http://localhost/api/ai/generate-title', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });

    const response = await POST(req);
    const responseBody = (await response.json()) as GenerateTitleResponse;

    expect(response.status).toBe(200);
    const fetchCallArgs = (global.fetch as Mock).mock.calls[0];
    const fetchBody = JSON.parse(fetchCallArgs[1].body as string);
    expect(fetchBody.content_blocks).toEqual(mockEmptyContentBlocks);
    expect(fetchBody.existing_title).toBeUndefined();
    expect(responseBody.suggested_title).toBe(mockSuggestedTitle);
  });
}); 