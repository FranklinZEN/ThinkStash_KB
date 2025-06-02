/**
 * @vitest-environment node
 */
/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { POST } from '@/app/api/ai/rewrite-content/route';
import { NextRequest } from 'next/server';
import {
  RewriteContentRequest,
  RewriteContentResponse,
  ContentBlock,
  DocumentMetadata,
} from '@/types/api/ai-service';

// Mocks for next/headers and next-auth (similar to reconstructAndAnalyze.test.ts)
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

describe('/api/ai/rewrite-content POST', () => {
  let originalFetch: typeof global.fetch;
  let originalProcessEnv: NodeJS.ProcessEnv;

  const mockUserId = 'test-user-session-id';
  const sampleContentBlocks: ContentBlock[] = [
    { block_id: 'cb1', type: 'text', text_content: 'This is the first block to rewrite.' },
    { block_id: 'cb2', type: 'text', text_content: 'This is the second block.' },
  ];
  const sampleDocumentMetadata: DocumentMetadata = {
    original_title: 'Test Document',
    source_url: 'https://example.com/original-doc',
  };

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

  it('should successfully rewrite content and return the mapped response', async () => {
    const mockPythonResponsePayload: RewriteContentResponse = {
      rewritten_document_id: 'rewritten-doc-123',
      ai_rewritten_content_blocks: [
        { block_id: 'rcb1', type: 'text', text_content: 'Rewritten first block.' },
      ],
      status_code: 'success',
      processing_time_ms: 1500,
      error_message: null,
    };

    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponsePayload, // Python service returns fields matching RewriteContentResponse
      status: 200,
    } as Response);

    const requestBody: RewriteContentRequest = {
      content_blocks_to_rewrite: sampleContentBlocks,
      document_metadata: sampleDocumentMetadata,
      // user_id can be in request, but route prioritizes session user_id
    };
    const req = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });

    const response = await POST(req);
    const responseBody = (await response.json()) as RewriteContentResponse;

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      `${process.env.AISERVICE_URL}/rewrite-content`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.any(String),
      })
    );

    const fetchCallArgs = (global.fetch as Mock).mock.calls[0];
    const fetchBody = JSON.parse(fetchCallArgs[1].body as string);
    expect(fetchBody).toEqual({
      content_blocks_to_rewrite: sampleContentBlocks,
      document_metadata: sampleDocumentMetadata,
      user_id: mockUserId, // Should use session user ID
    });

    expect(responseBody).toEqual(mockPythonResponsePayload);
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetServerSession.mockResolvedValue(null);
    const req = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify({ content_blocks_to_rewrite: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(401);
    expect(responseBody).toEqual({ error: 'Unauthorized' });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('should return 400 if content_blocks_to_rewrite is missing', async () => {
    const req = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify({ document_metadata: sampleDocumentMetadata }), // Missing content_blocks
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(400);
    expect(responseBody.error).toContain('content_blocks_to_rewrite is required');
  });

  it('should return 400 if content_blocks_to_rewrite is not an array', async () => {
    const req = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify({ content_blocks_to_rewrite: 'not-an-array' }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(400);
    expect(responseBody.error).toBe('Invalid request body: content_blocks_to_rewrite is required and must be an array.');
  });
  
  it('should use fallback AISERVICE_URL and succeed if process.env.AISERVICE_URL is undefined', async () => {
    const fallbackAIServiceURL = 'http://localhost:8000'; // Default in route.ts
    delete process.env.AISERVICE_URL;
    const mockPythonResponse = { ai_rewritten_content_blocks: [] }; // Minimal success
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true, status: 200, json: async () => mockPythonResponse
    } as Response);

    const req = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify({ content_blocks_to_rewrite: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    await POST(req);
    expect(global.fetch).toHaveBeenCalledWith(
      `${fallbackAIServiceURL}/rewrite-content`,
      expect.any(Object)
    );
  });

  it('should handle Python service error (e.g., 500) with JSON response', async () => {
    const pythonErrorResponse = { message: 'Python rewrite failed badly' };
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => pythonErrorResponse,
      status: 500,
    } as Response);
    const req = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify({ content_blocks_to_rewrite: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(500);
    expect(responseBody.error).toBe('Python aiservice failed to rewrite content.');
    expect(responseBody.details).toBe(pythonErrorResponse.message);
  });

  it('should handle Python service error with non-JSON response (e.g., 502)', async () => {
    const pythonErrorText = 'Gateway Timeout From Python';
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => { throw new Error("Not JSON"); },
      text: async () => pythonErrorText,
      status: 502,
      headers: new Headers(), redirected: false, type: 'basic', url: 'mockurl',
      clone: vi.fn(), arrayBuffer: vi.fn(), blob: vi.fn(), formData: vi.fn(), body: null, bodyUsed: false,
    } as unknown as Response);
    const req = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify({ content_blocks_to_rewrite: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(502);
    expect(responseBody.error).toBe('Python aiservice failed to rewrite content.');
    expect(responseBody.details).toBe(pythonErrorText);
  });

  it('should handle network error when fetching from Python service (fetch rejected)', async () => {
    (global.fetch as Mock).mockRejectedValueOnce(new TypeError('Network fetch failed'));
    const req = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify({ content_blocks_to_rewrite: sampleContentBlocks }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(503);
    expect(responseBody.error).toBe('Failed to connect to Python aiservice.');
    expect(responseBody.details).toBe('Network fetch failed');
  });

  it('should prioritize session user_id even if request body contains a different user_id', async () => {
    const requestBodyWithDifferentUserId: RewriteContentRequest = {
      content_blocks_to_rewrite: sampleContentBlocks,
      user_id: 'user-id-from-request-body', // Different from session mockUserId
    };
    const mockPythonResponsePayload = { ai_rewritten_content_blocks: [] }; // Minimal success

    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponsePayload,
      status: 200,
    } as Response);

    const req = new NextRequest('http://localhost/api/ai/rewrite-content', {
      method: 'POST',
      body: JSON.stringify(requestBodyWithDifferentUserId),
      headers: { 'Content-Type': 'application/json' },
    });

    await POST(req);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const fetchCallArgs = (global.fetch as Mock).mock.calls[0];
    const fetchBody = JSON.parse(fetchCallArgs[1].body as string);
    expect(fetchBody.user_id).toBe(mockUserId); // Assert that session user_id was used
    expect(fetchBody.user_id).not.toBe('user-id-from-request-body');
  });
}); 