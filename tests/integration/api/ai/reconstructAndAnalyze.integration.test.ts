/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { POST } from '@/app/api/ai/reconstruct-and-analyze/route'; // Adjust path if necessary
import { NextRequest } from 'next/server';
import {
  type ContentBlock,
  type ReconstructAndAnalyzeRequest, // For the Next.js route request
  type AIServiceReconstructAndAnalyzeRequest, // For the Python service request
  type OrchestrationOutput,          // For Python service response
  type NextJSReconstructAndAnalyzeResponse, // For the Next.js route response
  type DocumentMetadata
} from '@/types/api/ai-service';

// Mock next-auth
vi.mock('@/lib/auth', () => ({
  authOptions: {}, // Minimal mock, adjust if your authOptions has structure needed at import time
}));

// Hoist the mock function for getServerSession
const { mockGetServerSession } = vi.hoisted(() => {
  return { mockGetServerSession: vi.fn() };
});

vi.mock('next-auth/next', () => ({
  getServerSession: mockGetServerSession,
}));

// Mock global fetch
global.fetch = vi.fn();

// Store original environment variables
const originalEnv = { ...process.env };
const mockUserId = 'test-user-id'; // Defined for use in ContentBlock mocks
const mockDocumentId = 'test-doc-id'; // Defined for use in ContentBlock mocks

describe('/api/ai/reconstruct-and-analyze', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    process.env = { ...originalEnv }; // Reset environment variables

    // Default mock for successful authentication
    mockGetServerSession.mockResolvedValue({
      user: { id: mockUserId, email: 'test@example.com' },
      expires: 'some-future-date',
    });

    // Default AISERVICE_URL
    process.env.AISERVICE_URL = 'http://mock-aiservice:8000';
  });

  afterEach(() => {
    process.env = originalEnv; // Restore original environment variables
  });

  describe('POST', () => {
    it('should successfully reconstruct content from a URL and return the mapped OrchestrationOutput', async () => {
      const sourceUrl = 'https://example.com/article';
      const mockPythonResponse: OrchestrationOutput = {
        document_id: 'python-doc-id-123',
        user_id: mockUserId,
        status_code: 'success',
        source_identifier: sourceUrl, // This field from OrchestrationOutput might represent the input
        source_type: 'url',
        processing_level_used: 'full_content',
        extracted_title: 'Test Article Title',
        is_long_article: false,
        original_content_blocks: [{ block_id: 'b1', type: 'text', content: 'Hello world', user_id: mockUserId, document_id: mockDocumentId }], // Corrected field and added required fields
        processed_images_data: {},
        document_metadata: { title: 'Test Article Title', source_url: sourceUrl }, // Corrected: removed original_title
        error_message: null,
      };

      (fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockPythonResponse,
        status: 200,
      } as Response);

      // Next.js API request payload
      const nextApiRequestPayload: ReconstructAndAnalyzeRequest = { source_url: sourceUrl };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(nextApiRequestPayload),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody: NextJSReconstructAndAnalyzeResponse = await response.json();

      expect(response.status).toBe(200);
      expect(fetch).toHaveBeenCalledTimes(1);

      const fetchCallArgs = (fetch as Mock).mock.calls[0];
      const pythonServiceRequestBody: AIServiceReconstructAndAnalyzeRequest = JSON.parse(fetchCallArgs[1].body as string);

      expect(fetchCallArgs[0]).toBe(`${process.env.AISERVICE_URL}/reconstruct_and_analyze`); // Corrected endpoint
      expect(pythonServiceRequestBody).toEqual({
        source_url: sourceUrl, // Corrected: AIServiceReconstructAndAnalyzeRequest takes source_url
        source_type: 'url',
        user_id: mockUserId,
        job_id: expect.any(String),
      });

      // Asserting the Next.js API response structure
      expect(responseBody).toEqual({
        reconstruction_id: mockPythonResponse.document_id,
        status_code: mockPythonResponse.status_code,
        source_identifier: mockPythonResponse.source_identifier,
        document_metadata: mockPythonResponse.document_metadata,
        is_long_article: mockPythonResponse.is_long_article,
        original_content_blocks: mockPythonResponse.original_content_blocks,
        error_message: mockPythonResponse.error_message,
        // Ensure other fields from NextJSReconstructAndAnalyzeResponse are checked if they exist
      });
    });

    it('should successfully reconstruct content from a File ID and return the mapped OrchestrationOutput', async () => {
      const fileId = 'test-file-id-xyz789';
      const mockPythonResponse: OrchestrationOutput = {
        document_id: 'python-doc-id-456',
        user_id: mockUserId,
        status_code: 'success',
        source_identifier: fileId,
        source_type: 'file',
        processing_level_used: 'full_content',
        extracted_title: 'Test File Document Title',
        is_long_article: true,
        original_content_blocks: [{ block_id: 'fb1', type: 'text', content: 'Content from file.', user_id: mockUserId, document_id: mockDocumentId }], // Corrected field and added required fields
        processed_images_data: {},
        document_metadata: { title: 'Test File Document Title', source_url: undefined }, // Corrected: removed original_title
        error_message: null,
      };

      (fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockPythonResponse,
        status: 200,
      } as Response);

      const nextApiRequestPayload: ReconstructAndAnalyzeRequest = { file_id: fileId };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(nextApiRequestPayload),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody: NextJSReconstructAndAnalyzeResponse = await response.json();

      expect(response.status).toBe(200);
      expect(fetch).toHaveBeenCalledTimes(1);

      const fetchCallArgs = (fetch as Mock).mock.calls[0];
      const pythonServiceRequestBody: AIServiceReconstructAndAnalyzeRequest = JSON.parse(fetchCallArgs[1].body as string);

      expect(fetchCallArgs[0]).toBe(`${process.env.AISERVICE_URL}/reconstruct_and_analyze`); // Corrected endpoint
      expect(pythonServiceRequestBody).toEqual({
        file_id: fileId, // Corrected: AIServiceReconstructAndAnalyzeRequest takes file_id
        source_type: 'file',
        user_id: mockUserId,
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

    it('should successfully reconstruct content from text_content and return the mapped OrchestrationOutput', async () => {
      const textContent = "This is some direct text content.";
      const mockPythonResponse: OrchestrationOutput = {
        document_id: 'python-doc-id-789',
        user_id: mockUserId,
        status_code: 'success',
        source_identifier: 'text_input_identifier', // Or however Python service identifies text input
        source_type: 'text',
        processing_level_used: 'full_content',
        extracted_title: 'Title from Text',
        is_long_article: false,
        original_content_blocks: [{ block_id: 'tb1', type: 'text', content: textContent, user_id: mockUserId, document_id: mockDocumentId }],
        processed_images_data: {},
        document_metadata: { title: 'Title from Text' },
        error_message: null,
      };

      (fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockPythonResponse,
        status: 200,
      } as Response);

      // Next.js API request payload with text_content
      const nextApiRequestPayload: ReconstructAndAnalyzeRequest = { text_content: textContent };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(nextApiRequestPayload),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody: NextJSReconstructAndAnalyzeResponse = await response.json();

      expect(response.status).toBe(200);
      expect(fetch).toHaveBeenCalledTimes(1);

      const fetchCallArgs = (fetch as Mock).mock.calls[0];
      const pythonServiceRequestBody: AIServiceReconstructAndAnalyzeRequest = JSON.parse(fetchCallArgs[1].body as string);

      expect(fetchCallArgs[0]).toBe(`${process.env.AISERVICE_URL}/reconstruct_and_analyze`);
      expect(pythonServiceRequestBody).toEqual({
        text_content: textContent, // AIServiceReconstructAndAnalyzeRequest takes text_content
        source_type: 'text',
        user_id: mockUserId,
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
      mockGetServerSession.mockResolvedValueOnce(null);

      const requestBody: ReconstructAndAnalyzeRequest = { source_url: 'https://example.com/article' };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(401);
      expect(responseBody).toEqual({ error: 'Unauthorized' });
      expect(fetch).not.toHaveBeenCalled();
    });

    it('should return 500 if AISERVICE_URL is not set (route uses fallback, so this test might need adjustment or indicates route logic change)', async () => {
      // If the route has a fallback for AISERVICE_URL, this test's expectation of 500 might be incorrect.
      // The route from the previous context had: const AISERVICE_URL = process.env.AISERVICE_URL || 'http://localhost:8000';
      // If that's still the case, deleting process.env.AISERVICE_URL would make it use the fallback,
      // and the test should mock a successful call to the fallback or a failure from the fallback.
      // For this iteration, assuming the intent is to test if the PRIMARY URL is missing AND there's NO fallback handling in this specific route version.
      delete process.env.AISERVICE_URL;

      const requestBody: ReconstructAndAnalyzeRequest = { source_url: 'https://example.com/article' };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      // This expectation depends on the route's actual behavior when AISERVICE_URL is missing.
      // If it errors out due to missing config (and no fallback), 500 is plausible.
      expect(response.status).toBe(500); // Or another status if route handles this differently
      expect(responseBody.error).toMatch(/AI service configuration error/i); // Adjusted message
      expect(fetch).not.toHaveBeenCalled();
    });


    it('should return 400 if source_url, file_id, or text_content are missing', async () => {
      const requestBody = {}; // Empty body, missing all primary source fields
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(400);
      // Message should reflect that one of the valid source types is required.
      expect(responseBody.error).toMatch(/Invalid request body: source_url, file_id, or text_content is required/i);
      expect(fetch).not.toHaveBeenCalled();
    });

    it('should return 400 if multiple source types are provided (e.g., source_url and file_id)', async () => {
      const requestBody: ReconstructAndAnalyzeRequest = { source_url: 'https://example.com/article', file_id: 'some-file-id' };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(400);
      expect(responseBody.error).toMatch(/Invalid request body: provide only one of source_url, file_id, or text_content/i);
      expect(fetch).not.toHaveBeenCalled();
    });

    it('should handle Python service error (500) with JSON response', async () => {
      const sourceUrl = 'https://example.com/article-causing-error';
      const pythonErrorResponse = {
        message: 'Python internal server error',
        code: 'PYTHON_ERROR_XYZ'
      };

      (fetch as Mock).mockResolvedValueOnce({
        ok: false,
        json: async () => pythonErrorResponse,
        status: 500,
        statusText: 'Internal Server Error',
      } as Response);

      const nextApiRequestPayload: ReconstructAndAnalyzeRequest = { source_url: sourceUrl };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(nextApiRequestPayload),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(500);
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(responseBody.error).toBe('Python aiservice failed to reconstruct and analyze content.');
      expect(responseBody.details).toBe(pythonErrorResponse.message);
      expect(responseBody.reconstruction_id).toEqual(expect.any(String));
    });

    it('should handle Python service error with non-JSON response', async () => {
      const sourceUrl = 'https://example.com/article-causing-text-error';
      const pythonErrorText = 'Python service unavailable: Gateway Timeout';

      (fetch as Mock).mockResolvedValueOnce({
        ok: false,
        json: async () => { throw new Error("Not JSON"); },
        text: async () => pythonErrorText,
        status: 502,
        statusText: 'Bad Gateway',
        headers: new Headers(),
        redirected: false,
        type: 'basic',
        url: `${process.env.AISERVICE_URL}/reconstruct_and_analyze`,
        clone: vi.fn(),
        arrayBuffer: vi.fn(),
        blob: vi.fn(),
        formData: vi.fn(),
        body: null,
        bodyUsed: false,
      } as unknown as Response);

      const nextApiRequestPayload: ReconstructAndAnalyzeRequest = { source_url: sourceUrl };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(nextApiRequestPayload),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(502);
      expect(responseBody.error).toBe('Python aiservice failed to reconstruct and analyze content.');
      expect(responseBody.details).toBe(pythonErrorText);
      expect(responseBody.reconstruction_id).toEqual(expect.any(String));
    });

    it('should handle network error when fetching from Python service', async () => {
      const sourceUrl = 'https://example.com/article-network-error';

      (fetch as Mock).mockRejectedValueOnce(new TypeError('fetch failed'));

      const nextApiRequestPayload: ReconstructAndAnalyzeRequest = { source_url: sourceUrl };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(nextApiRequestPayload),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(503);
      expect(responseBody.error).toBe('Failed to connect to Python aiservice.');
      expect(responseBody.details).toBe('fetch failed');
    });
  });
});