/**
 * @vitest-environment node
 */
/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { POST } from '@/app/api/ai/reconstruct-and-analyze/route';
import { NextRequest } from 'next/server';
import { OrchestrationOutput } from '@/types/api/ai-service';
// getServerSession is effectively mocked, so we don't need to import it directly here for casting
// import { getServerSession } from 'next-auth'; 
// import { NextResponse } from 'next/server'; // Unused import

// Define mock functions for next/headers before vi.mock call
const mockHeadersInstance = new Headers({ 'x-test-header': 'test' });
const mockHeadersFn = vi.fn(() => mockHeadersInstance);

const mockCookiesGetFn = vi.fn();
const mockCookiesHasFn = vi.fn();
const mockCookiesSetFn = vi.fn();
const mockCookiesDeleteFn = vi.fn();
const mockCookiesGetAllFn = vi.fn(() => []); // ReadonlyRequestCookies often has getAll
const mockCookiesClearFn = vi.fn(); // and clear
const mockCookiesIteratorFn = vi.fn(function*() {}); // Make it iterable

const mockCookiesObject = {
  get: mockCookiesGetFn,
  has: mockCookiesHasFn,
  set: mockCookiesSetFn,
  delete: mockCookiesDeleteFn,
  getAll: mockCookiesGetAllFn,
  clear: mockCookiesClearFn,
  [Symbol.iterator]: mockCookiesIteratorFn,
  // Add other ReadonlyRequestCookies properties/methods if needed by next-auth
  // e.g., size: 0 (though typically methods are called)
};
const mockCookiesFn = vi.fn(() => mockCookiesObject);


// Mock next/headers to prevent "called outside a request scope" error
vi.mock('next/headers', () => ({
  __esModule: true,
  headers: mockHeadersFn,
  cookies: mockCookiesFn,
  // If other exports like RequestCookies class are needed by the code under test or next-auth,
  // they would need to be mocked or provided here.
  // For now, assuming only headers() and cookies() calls are made by getServerSession internals.
}));

// Use vi.hoisted to ensure mockGetServerSession is initialized before being used in the vi.mock factory
const { mockGetServerSession } = vi.hoisted(() => {
  return { mockGetServerSession: vi.fn() };
});

// Mock NextAuth with a specific factory to ensure getServerSession is our mock
vi.mock('next-auth/next', () => ({
  __esModule: true, // If next-auth is an ES module
  getServerSession: mockGetServerSession,
}));

// Mock the authOptions that are imported in the actual API route from @/lib/auth
vi.mock('@/lib/auth', () => ({
  authOptions: {},
}));

// Default mock environment variables. AISERVICE_URL will be specifically set/unset in tests as needed.
const baseMockEnv = {}; 

describe('/api/ai/reconstruct-and-analyze POST', () => {
  let originalFetch: typeof global.fetch;
  let originalProcessEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    // Save original process.env and restore it for each test
    originalProcessEnv = { ...process.env };
    // Stub global process.env for this test suite
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
    (mockCookiesIteratorFn as Mock).mockClear(); // Use imported Mock type

    originalFetch = global.fetch;
    global.fetch = vi.fn();

    // Default successful authentication for most tests
    mockGetServerSession.mockResolvedValue({
      user: { id: 'test-user-id', email: 'test@example.com' },
      expires: 'some-future-date',
    });
    
    // Default AISERVICE_URL for most tests
    process.env.AISERVICE_URL = 'http://mock-aiservice-url.com';
  });

  afterEach(() => {
    global.fetch = originalFetch;
    // Restore original process.env by unstubbing and then setting it back if needed, 
    // or simply by unstubbing if the stubGlobal was comprehensive.
    vi.unstubAllGlobals(); 
    process.env = originalProcessEnv; // Explicitly restore
  });

  it('should successfully reconstruct content from a URL and return the mapped OrchestrationOutput', async () => {
    const sourceUrl = 'https://example.com/article';
    const mockPythonResponse: OrchestrationOutput = {
      document_id: 'python-doc-id-123',
      user_id: 'test-user-id',
      status_code: 'success',
      source_identifier: sourceUrl,
      source_type: 'url',
      processing_level_used: 'full_content',
      extracted_title: 'Test Article Title',
      is_long_article: false,
      original_content_blocks: [{ block_id: 'b1', type: 'text', text_content: 'Hello world' }],
      processed_images_data: {},
      document_metadata: { original_title: 'Test Article Title', source_url: sourceUrl },
      error_message: null,
    };

    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponse,
      status: 200,
    } as Response);

    const requestBody = { source_url: sourceUrl };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });

    const response = await POST(req);
    const responseBody = await response.json();

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      `${process.env.AISERVICE_URL}/reconstruct-and-analyze`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.any(String),
      })
    );
    const fetchCallArgs = (global.fetch as Mock).mock.calls[0];
    const fetchBody = JSON.parse(fetchCallArgs[1].body as string);
    expect(fetchBody).toEqual({
      source_identifier: sourceUrl,
      source_type: 'url',
      user_id: 'test-user-id',
      job_id: expect.any(String),
    });
    expect(responseBody).toEqual({
      reconstruction_id: mockPythonResponse.document_id,
      status_code: mockPythonResponse.status_code,
      source_identifier: mockPythonResponse.source_identifier,
      document_metadata: mockPythonResponse.document_metadata,
      is_long_article: mockPythonResponse.is_long_article,
      original_content_blocks: mockPythonResponse.original_content_blocks,
      error_message: mockPythonResponse.error_message,
    });
  });

  it('should successfully reconstruct content from a File ID and return the mapped OrchestrationOutput', async () => {
    const fileId = 'test-file-id-xyz789';
    const mockPythonResponse: OrchestrationOutput = {
      document_id: 'python-doc-id-456',
      user_id: 'test-user-id',
      status_code: 'success',
      source_identifier: fileId,
      source_type: 'file',
      processing_level_used: 'full_content',
      extracted_title: 'Test File Document Title',
      is_long_article: true,
      original_content_blocks: [{ block_id: 'fb1', type: 'text', text_content: 'Content from file.' }],
      processed_images_data: {},
      document_metadata: { original_title: 'Test File Document Title', source_url: undefined },
      error_message: null,
    };
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponse,
      status: 200,
    } as Response);
    const requestBody = { file_id: fileId };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      `${process.env.AISERVICE_URL}/reconstruct-and-analyze`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.any(String),
      })
    );
    const fetchCallArgsFile = (global.fetch as Mock).mock.calls[0];
    const fetchBodyFile = JSON.parse(fetchCallArgsFile[1].body as string);
    expect(fetchBodyFile).toEqual({
      source_identifier: fileId,
      source_type: 'file',
      user_id: 'test-user-id',
      job_id: expect.any(String),
    });
    expect(responseBody).toEqual({
      reconstruction_id: mockPythonResponse.document_id,
      status_code: mockPythonResponse.status_code,
      source_identifier: mockPythonResponse.source_identifier,
      document_metadata: mockPythonResponse.document_metadata,
      is_long_article: mockPythonResponse.is_long_article,
      original_content_blocks: mockPythonResponse.original_content_blocks,
      error_message: mockPythonResponse.error_message,
    });
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetServerSession.mockResolvedValue(null);
    const request = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify({ source_url: 'http://example.com' }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(request);
    const responseBody = await response.json();
    expect(response.status).toBe(401);
    expect(responseBody).toEqual({ error: 'Unauthorized' });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('should use fallback AISERVICE_URL and succeed if process.env.AISERVICE_URL is undefined', async () => {
    // Route uses: const AISERVICE_URL = process.env.AISERVICE_URL || 'http://localhost:8000';
    const fallbackAIServiceURL = 'http://localhost:8000';
    delete process.env.AISERVICE_URL;

    const sourceUrl = 'https://example.com/article-fallback';
    const mockPythonResponse: OrchestrationOutput = { /* ... minimal valid mock ... */ 
      document_id: 'fallback-doc-id', status_code: 'success', source_identifier: sourceUrl, source_type: 'url', is_long_article: false, original_content_blocks: [], error_message: null
    };
    (global.fetch as Mock).mockResolvedValueOnce({
        ok: true, status: 200, json: async () => mockPythonResponse, headers: new Headers({'Content-Type': 'application/json'})} as Response);

    const request = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify({ source_url: sourceUrl }),
      headers: { 'Content-Type': 'application/json' }, 
    });
    const response = await POST(request);
    const responseBody = await response.json();
    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledWith(
      `${fallbackAIServiceURL}/reconstruct-and-analyze`, // Expect call to fallback URL
      expect.any(Object)
    );
    expect(responseBody.reconstruction_id).toBe('fallback-doc-id');
  });

  it('should return 400 if both source_url and file_id are missing', async () => {
    const requestBody = {};
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(400);
    expect(responseBody).toEqual({ error: 'Invalid request body: source_url or file_id is required.' });
    expect(global.fetch).not.toHaveBeenCalled();
  });
  
  it('should return 400 if both source_url and file_id are provided', async () => {
    const requestBody = { source_url: 'https://example.com/article', file_id: 'some-file-id' };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(400);
    expect(responseBody).toEqual({ error: 'Invalid request body: provide either source_url or file_id, not both.' });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('should handle Python service error (e.g., 500) with JSON response', async () => {
    const sourceUrl = 'https://example.com/article-causing-error';
    const pythonErrorResponse = { message: 'Python internal server error', code: 'PYTHON_ERROR_XYZ' };
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => pythonErrorResponse,
      status: 500,
      statusText: 'Internal Server Error',
    } as Response);
    const requestBody = { source_url: sourceUrl };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(500);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(responseBody).toEqual({
      error: 'Python aiservice failed to reconstruct and analyze content.',
      details: pythonErrorResponse.message,
      reconstruction_id: expect.any(String),
    });
  });
  
  it('should handle Python service error with non-JSON response (e.g., 502 Bad Gateway)', async () => {
    const sourceUrl = 'https://example.com/article-causing-text-error';
    const pythonErrorText = 'Python service unavailable: Gateway Timeout';
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => { throw new Error("Not JSON"); },
      text: async () => pythonErrorText,
      status: 502,
      statusText: 'Bad Gateway',
      headers: new Headers(),
      redirected: false,
      type: 'basic',
      url: `${process.env.AISERVICE_URL}/reconstruct-and-analyze`,
      clone: vi.fn(), arrayBuffer: vi.fn(), blob: vi.fn(), formData: vi.fn(), body: null, bodyUsed: false,
    } as unknown as Response);
    const requestBody = { source_url: sourceUrl };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(502);
    expect(responseBody).toEqual({
      error: 'Python aiservice failed to reconstruct and analyze content.',
      details: pythonErrorText,
      reconstruction_id: expect.any(String),
    });
  });

  it('should handle network error when fetching from Python service (fetch rejected)', async () => {
    const sourceUrl = 'https://example.com/article-network-error';
    (global.fetch as Mock).mockRejectedValueOnce(new TypeError('fetch failed'));
    const requestBody = { source_url: sourceUrl };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(503);
    expect(responseBody).toEqual({
      error: 'Failed to connect to Python aiservice.',
      details: 'fetch failed',
    });
  });
}); 