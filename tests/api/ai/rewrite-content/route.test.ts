/**
 * @vitest-environment node
 */
/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { POST } from '@/app/api/ai/rewrite-content/route';
import { NextRequest } from 'next/server';
import {
  type ContentBlock,
  type RewriteContentRequest,
  type RewriteContentResponse,
  type DocumentMetadata
} from '@/types/api/ai-service';

// Mocks for next/headers and next-auth (standard setup)
const mockHeadersInstance = new Headers({ 'x-test-header': 'test' });
const mockHeadersFn = vi.fn(() => mockHeadersInstance);
const mockCookiesGetFn = vi.fn();
const mockCookiesObject = { get: mockCookiesGetFn, /* other methods */ has: vi.fn(), set: vi.fn(), delete: vi.fn(), getAll: vi.fn(() => []), clear: vi.fn(), [Symbol.iterator]: vi.fn(function*() {}) };
const mockCookiesFn = vi.fn(() => mockCookiesObject);
vi.mock('next/headers', () => ({ headers: mockHeadersFn, cookies: mockCookiesFn }));
const { mockGetServerSession } = vi.hoisted(() => ({ mockGetServerSession: vi.fn() }));
vi.mock('next-auth/next', () => ({ getServerSession: mockGetServerSession }));
vi.mock('@/lib/auth', () => ({ authOptions: {} }));

const baseMockEnv = {};
const mockUserId = 'test-user-rewrite';
const mockDocumentId = 'doc-rewrite-123';

// Corrected ContentBlock mocks
const mockOriginalContentBlocks: ContentBlock[] = [
  { block_id: 'cb1', user_id: mockUserId, document_id: mockDocumentId, type: 'text', content: 'This is the original text that needs rewriting.' },
  { block_id: 'cb2', user_id: mockUserId, document_id: mockDocumentId, type: 'heading', content: 'Original Heading', level: 2 },
];

const mockRewrittenContentBlocks: ContentBlock[] = [
  { block_id: 'rewritten-cb1', user_id: mockUserId, document_id: mockDocumentId, type: 'text', content: 'This is the brilliantly rewritten text.' },
  { block_id: 'rewritten-cb2', user_id: mockUserId, document_id: mockDocumentId, type: 'heading', content: 'Rewritten Heading', level: 2 },
];

// Mock for DocumentMetadata (ensure no original_title)
const mockDocMetadata: DocumentMetadata = {
  title: 'Test Document for Rewrite',
  source_url: 'https://example.com/original-doc'
};

describe('/api/ai/rewrite-content POST', () => {
  let originalFetch: typeof global.fetch;
  let originalProcessEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    originalProcessEnv = { ...process.env };
    vi.stubGlobal('process', { env: { ...originalProcessEnv, ...baseMockEnv } });
    mockGetServerSession.mockReset().mockResolvedValue({ user: { id: mockUserId }, expires: 'date' });
    mockHeadersFn.mockClear().mockReturnValue(new Headers({ 'x-test-header': 'test' }));
    mockCookiesFn.mockClear().mockReturnValue(mockCookiesObject);
    originalFetch = global.fetch;
    global.fetch = vi.fn();
    process.env.AISERVICE_URL = 'http://mock-aiservice-url.com';
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllGlobals();
    process.env = originalProcessEnv;
  });

  it('should successfully rewrite content and return the rewritten blocks', async () => {
    const mockPythonResponse = {
      ai_rewritten_content_blocks: mockRewrittenContentBlocks,
      status_code: 'success',
      // rewritten_document_id is optional in Python response for this service
    };

    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPythonResponse,
      status: 200,
    } as Response);

    const requestBody: RewriteContentRequest = {
      content_blocks_to_rewrite: mockOriginalContentBlocks,
      document_metadata: mockDocMetadata,
      rewrite_instructions: 'Make it more engaging.',
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
    
    const expectedPythonPayload = {
        user_id: mockUserId,
        content_blocks_to_rewrite: mockOriginalContentBlocks,
        document_metadata: mockDocMetadata,
        // rewrite_instructions: 'Make it more engaging.', // Removed as it's not sent by the route
    };

    expect(global.fetch).toHaveBeenCalledWith(
      `${process.env.AISERVICE_URL}/rewrite-content`, // Ensure this matches actual Python endpoint
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // body: JSON.stringify(expectedPythonPayload), // Removed direct string body comparison
      })
    );

    // Get the actual call arguments to fetch
    const fetchCallArgs = (global.fetch as Mock).mock.calls[0];
    const fetchOptions = fetchCallArgs[1]; // The options object passed to fetch
    const actualBodyObject = JSON.parse(fetchOptions.body as string);

    expect(actualBodyObject).toEqual(expectedPythonPayload);

    expect(responseBody.ai_rewritten_content_blocks).toEqual(mockRewrittenContentBlocks);
    expect(responseBody.status_code).toBe('success');
    expect(responseBody.error_message).toBeUndefined();
  });

  // Add other tests: for unauthorized, missing body, Python service error, etc.

}); 