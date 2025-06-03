/**
 * @vitest-environment node
 */
/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { POST } from '@/app/api/ai/reconstruct-and-analyze/route';
import { NextRequest } from 'next/server';
import {
  type ContentBlock,
  type ReconstructAndAnalyzeRequest, // For the Next.js route
  type OrchestrationOutput,          // For mocking Python service response
  type DocumentMetadata,
  type AIServiceReconstructAndAnalyzeRequest, // For the call to the Python service
  type NextJSReconstructAndAnalyzeResponse // For the Next.js route response
} from '@/types/api/ai-service';
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

const mockUserIdForBlocks = 'test-user-reconstruct'; // User ID used within some mock block data
const mockDocumentIdForBlockContext = 'test-doc-reconstruct'; // Used for context within blocks, not sent in Next.js request
// const mockJobId = 'job-123'; // job_id is generated dynamically

const mockContentBlocksSimple: ContentBlock[] = [
  { block_id: 'cb1', user_id: mockUserIdForBlocks, document_id: mockDocumentIdForBlockContext, type: 'text', content: 'First basic block.' },
  { block_id: 'cb2', user_id: mockUserIdForBlocks, document_id: mockDocumentIdForBlockContext, type: 'text', content: 'Second basic block.' },
];

const mockContentBlocksWithStructure: ContentBlock[] = [
  { block_id: 'cb3', user_id: mockUserIdForBlocks, document_id: mockDocumentIdForBlockContext, type: 'heading', content: 'Main Heading', level: 1 },
  { block_id: 'cb4', user_id: mockUserIdForBlocks, document_id: mockDocumentIdForBlockContext, type: 'text', content: 'Some paragraph text under heading.' },
  { block_id: 'cb5', user_id: mockUserIdForBlocks, document_id: mockDocumentIdForBlockContext, type: 'list_item', content: 'Item 1' },
  { block_id: 'cb6', user_id: mockUserIdForBlocks, document_id: mockDocumentIdForBlockContext, type: 'list_item', content: 'Item 2' },
];

// Mock for DocumentMetadata without original_title
const mockDocMetadata: DocumentMetadata = {
  title: 'Test Article Title',
  source_url: 'https://example.com/article'
};

// Mock for OrchestrationOutput (Python service response)
// This is used in the first test.
const mockPythonResponseForGeneralTest: OrchestrationOutput = {
  document_id: 'python-doc-id-123',
  user_id: 'test-user-id', // Should match session user ID if Python service echoes it
  status_code: 'success',
  source_identifier: 'https://example.com/article',
  source_type: 'url',
  processing_level_used: 'full_content',
  extracted_title: 'Test Article Title',
  is_long_article: false,
  original_content_blocks: mockContentBlocksSimple, // These blocks use mockUserIdForBlocks
  processed_images_data: {},
  document_metadata: mockDocMetadata,
  error_message: null,
};

describe('/api/ai/reconstruct-and-analyze POST', () => {
  let originalFetch: typeof global.fetch;
  let originalProcessEnv: NodeJS.ProcessEnv;
  const sessionUserId = 'test-user-id'; // User ID from mocked session

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
      user: { id: sessionUserId, email: 'test@example.com' },
      expires: 'some-future-date',
    });

    process.env.AISERVICE_URL = 'http://mock-aiservice-url.com';
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllGlobals();
    process.env = originalProcessEnv;
  });

  it('should successfully call Python service and return mapped response for URL source', async () => {
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponseForGeneralTest,
      status: 200,
    } as Response);

    const nextApiRequestPayload: ReconstructAndAnalyzeRequest = {
      source_url: 'https://example.com/article',
    };

    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(nextApiRequestPayload),
      headers: { 'Content-Type': 'application/json' },
    });

    const response = await POST(req);
    const responseBody: NextJSReconstructAndAnalyzeResponse = await response.json();

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    const pythonCallArgs = (global.fetch as Mock).mock.calls[0];
    const pythonRequestBody: AIServiceReconstructAndAnalyzeRequest = JSON.parse(pythonCallArgs[1].body as string);

    // Assertions for the call to the Python service
    expect(pythonCallArgs[0]).toBe(`${process.env.AISERVICE_URL}/api/v1/ai/reconstruct-and-analyze`);
    expect(pythonRequestBody.source_url).toBe('https://example.com/article');
    expect(pythonRequestBody.source_type).toBe('url');
    expect(pythonRequestBody.user_id).toBe(sessionUserId);
    expect(pythonRequestBody.job_id).toEqual(expect.any(String));


    // Assertions for the Next.js API response to the client
    // Assuming NextJSReconstructAndAnalyzeResponse directly maps OrchestrationOutput fields
    // and renames document_id to reconstruction_id
    expect(responseBody).toEqual({
        reconstruction_id: mockPythonResponseForGeneralTest.document_id,
        status_code: mockPythonResponseForGeneralTest.status_code,
        source_identifier: mockPythonResponseForGeneralTest.source_identifier,
        document_metadata: mockPythonResponseForGeneralTest.document_metadata,
        is_long_article: mockPythonResponseForGeneralTest.is_long_article,
        original_content_blocks: mockPythonResponseForGeneralTest.original_content_blocks,
        error_message: mockPythonResponseForGeneralTest.error_message,
        // If NextJSReconstructAndAnalyzeResponse has a 'message' field, it should be asserted here
        // For example: message: 'Successfully initiated reconstruction and analysis.'
    });
  });

  it('should successfully reconstruct content from a URL and return the mapped OrchestrationOutput', async () => {
    const sourceUrl = 'https://example.com/article-specific';
    const mockPythonResponse: OrchestrationOutput = {
      document_id: 'python-doc-url-001',
      user_id: sessionUserId,
      status_code: 'success',
      source_identifier: sourceUrl,
      source_type: 'url',
      processing_level_used: 'full_content',
      extracted_title: 'Specific URL Title',
      is_long_article: false,
      original_content_blocks: [{ block_id: 'b1',user_id: mockUserIdForBlocks, document_id: mockDocumentIdForBlockContext, type: 'text', content: 'Hello world from URL' }],
      processed_images_data: {},
      document_metadata: { title: 'Specific URL Title', source_url: sourceUrl },
      error_message: null,
    };

    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponse,
      status: 200,
    } as Response);

    const requestBody: ReconstructAndAnalyzeRequest = { source_url: sourceUrl };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });

    const response = await POST(req);
    const responseBody: NextJSReconstructAndAnalyzeResponse = await response.json();

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      `${process.env.AISERVICE_URL}/api/v1/ai/reconstruct-and-analyze`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    );
    const fetchCallArgs = (global.fetch as Mock).mock.calls[0];
    const fetchBody: AIServiceReconstructAndAnalyzeRequest = JSON.parse(fetchCallArgs[1].body as string);

    expect(fetchBody).toEqual({
      source_url: sourceUrl,
      source_type: 'url',
      user_id: sessionUserId,
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
      document_id: 'python-doc-file-002',
      user_id: sessionUserId,
      status_code: 'success',
      source_identifier: fileId,
      source_type: 'file',
      processing_level_used: 'full_content',
      extracted_title: 'Test File Document Title',
      is_long_article: true,
      original_content_blocks: [{ block_id: 'fb1', user_id: mockUserIdForBlocks, document_id: mockDocumentIdForBlockContext, type: 'text', content: 'Content from file.' }],
      processed_images_data: {},
      document_metadata: { title: 'Test File Document Title', source_url: undefined },
      error_message: null,
    };
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponse,
      status: 200,
    } as Response);

    const requestBody: ReconstructAndAnalyzeRequest = { file_id: fileId };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody: NextJSReconstructAndAnalyzeResponse = await response.json();

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      `${process.env.AISERVICE_URL}/api/v1/ai/reconstruct-and-analyze`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    );
    const fetchCallArgsFile = (global.fetch as Mock).mock.calls[0];
    const fetchBodyFile: AIServiceReconstructAndAnalyzeRequest = JSON.parse(fetchCallArgsFile[1].body as string);

    expect(fetchBodyFile).toEqual({
      file_id: fileId,
      source_type: 'file',
      user_id: sessionUserId,
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
    const fallbackAIServiceURL = 'http://localhost:8000'; // Assuming this is the fallback in the route
    delete process.env.AISERVICE_URL;

    const sourceUrl = 'https://example.com/article-fallback';
    const mockPythonResponse: OrchestrationOutput = {
      document_id: 'fallback-doc-id', status_code: 'success', source_identifier: sourceUrl, user_id: sessionUserId,
      source_type: 'url', is_long_article: false, original_content_blocks: [], error_message: null,
      processing_level_used: 'full_content', extracted_title: 'Fallback Title', processed_images_data: {}, document_metadata: {title: 'Fallback Title'}
    };
    (global.fetch as Mock).mockResolvedValueOnce({
        ok: true, status: 200, json: async () => mockPythonResponse, headers: new Headers({'Content-Type': 'application/json'})} as Response);

    const request = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify({ source_url: sourceUrl }),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(request);
    const responseBody: NextJSReconstructAndAnalyzeResponse = await response.json();
    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledWith(
      `${fallbackAIServiceURL}/api/v1/ai/reconstruct-and-analyze`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    );
    expect(responseBody.reconstruction_id).toBe('fallback-doc-id');
  });

  it('should return 400 if source_url, file_id, or text_content are missing', async () => {
    const requestBody = {}; // Empty body
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(400);
    expect(responseBody.error).toMatch(/Invalid request body: source_url, file_id, or text_content is required./i);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('should return 400 if multiple source types are provided (e.g., source_url and file_id)', async () => {
    const requestBody: ReconstructAndAnalyzeRequest = { source_url: 'https://example.com/article', file_id: 'some-file-id' };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(400);
    expect(responseBody.error).toMatch(/Invalid request body: provide only one of source_url, file_id, or text_content./i);
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
    const requestBody: ReconstructAndAnalyzeRequest = { source_url: sourceUrl };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(500);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(responseBody.error).toBe('Python aiservice failed to reconstruct and analyze content.');
    expect(responseBody.details).toBe(pythonErrorResponse.message);
    expect(responseBody.reconstruction_id).toEqual(expect.any(String));
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
      url: `${process.env.AISERVICE_URL}/api/v1/ai/reconstruct-and-analyze`,
      clone: vi.fn(), arrayBuffer: vi.fn(), blob: vi.fn(), formData: vi.fn(), body: null, bodyUsed: false,
    } as unknown as Response);

    const requestBody: ReconstructAndAnalyzeRequest = { source_url: sourceUrl };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(502);
    expect(responseBody.error).toBe('Python aiservice failed to reconstruct and analyze content.');
    expect(responseBody.details).toBe(pythonErrorText);
    expect(responseBody.reconstruction_id).toEqual(expect.any(String));
  });

  it('should handle network error when fetching from Python service (fetch rejected)', async () => {
    const sourceUrl = 'https://example.com/article-network-error';
    (global.fetch as Mock).mockRejectedValueOnce(new TypeError('fetch failed'));
    const requestBody: ReconstructAndAnalyzeRequest = { source_url: sourceUrl };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });
    const response = await POST(req);
    const responseBody = await response.json();
    expect(response.status).toBe(503);
    expect(responseBody.error).toBe('Failed to connect to Python aiservice.');
    expect(responseBody.details).toBe('fetch failed');
  });

  // Test for handling text_content input derived from content_blocks
  it('should process text_content (derived from simple blocks) and return mapped OrchestrationOutput', async () => {
    // Convert mockContentBlocksSimple to a single text_content string
    const derivedTextContent = mockContentBlocksSimple.map(b => b.content).join('\n');

    const mockPythonResponse: OrchestrationOutput = {
      document_id: 'python-doc-from-derived-text-003',
      user_id: sessionUserId,
      status_code: 'success',
      source_identifier: derivedTextContent, // Python service might return the input text or a hash
      source_type: 'text', // Python service was called with text
      processing_level_used: 'full_content',
      extracted_title: 'Derived Title from Simple Text',
      is_long_article: false,
      // original_content_blocks could be the initial blocks or reconstructed ones by Python
      original_content_blocks: mockContentBlocksSimple,
      processed_images_data: {},
      document_metadata: { title: 'Derived Title from Simple Text' },
      error_message: null,
    };

    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponse,
      status: 200,
    } as Response);

    // Next.js API receives text_content
    const requestBody: ReconstructAndAnalyzeRequest = {
      text_content: derivedTextContent, // Pass the derived text content
    };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });

    const response = await POST(req);
    const responseBody: NextJSReconstructAndAnalyzeResponse = await response.json();

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      `${process.env.AISERVICE_URL}/api/v1/ai/reconstruct-and-analyze`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    );
    const fetchCallArgs = (global.fetch as Mock).mock.calls[0];
    const fetchBody: AIServiceReconstructAndAnalyzeRequest = JSON.parse(fetchCallArgs[1].body as string);

    // Python service is called with text_content
    expect(fetchBody).toEqual({
      user_id: sessionUserId,
      job_id: expect.any(String),
      source_type: 'text', // Ensure source_type is 'text'
      text_content: derivedTextContent, // Ensure text_content matches the derived string
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

  it('should process text_content (derived from complex blocks) and return mapped OrchestrationOutput', async () => {
    // Convert mockContentBlocksWithStructure to a single text_content string
    const derivedTextContentComplex = mockContentBlocksWithStructure.map(b => b.content).join('\n');

    const mockPythonResponse: OrchestrationOutput = {
      document_id: 'python-doc-from-derived-complex-text-004',
      user_id: sessionUserId,
      status_code: 'success',
      source_identifier: derivedTextContentComplex,
      source_type: 'text',
      processing_level_used: 'full_content',
      extracted_title: 'Derived Title from Complex Text',
      is_long_article: false,
      original_content_blocks: mockContentBlocksWithStructure,
      processed_images_data: {},
      document_metadata: { title: 'Derived Title from Complex Text' },
      error_message: null,
    };

    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponse,
      status: 200,
    } as Response);

    const requestBody: ReconstructAndAnalyzeRequest = {
      text_content: derivedTextContentComplex, // Pass the derived text content
    };
    const req = new NextRequest('http://localhost/api/ai/reconstruct-and-analyze', {
      method: 'POST',
      body: JSON.stringify(requestBody),
      headers: { 'Content-Type': 'application/json' },
    });

    const response = await POST(req);
    const responseBody: NextJSReconstructAndAnalyzeResponse = await response.json();

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      `${process.env.AISERVICE_URL}/api/v1/ai/reconstruct-and-analyze`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    );
    const fetchCallArgs = (global.fetch as Mock).mock.calls[0];
    const fetchBody: AIServiceReconstructAndAnalyzeRequest = JSON.parse(fetchCallArgs[1].body as string);

    expect(fetchBody).toEqual({
      user_id: sessionUserId,
      job_id: expect.any(String),
      source_type: 'text', // Ensure source_type is 'text'
      text_content: derivedTextContentComplex, // Ensure text_content matches the derived string
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
});
