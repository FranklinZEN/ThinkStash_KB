/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { POST } from '@/app/api/ai/reconstruct-and-analyze/route'; // Adjust path if necessary
import { NextRequest } from 'next/server';
import { OrchestrationOutput } from '@/types/api/ai-service'; // For typing the mock response

// Mock next-auth
vi.mock('@/lib/auth', () => ({
  authOptions: {}, // Minimal mock, adjust if your authOptions has structure needed at import time
}));

vi.mock('next-auth/next', () => ({
  getServerSession: vi.fn(),
}));

// Mock global fetch
global.fetch = vi.fn();

const mockGetServerSession = vi.mocked(require('next-auth/next').getServerSession);
// No need to reassign global.fetch to mockFetch, just use global.fetch directly with type assertion or vi.mocked()

// Store original environment variables
const originalEnv = { ...process.env };

describe('/api/ai/reconstruct-and-analyze', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    process.env = { ...originalEnv }; // Reset environment variables

    // Default mock for successful authentication
    mockGetServerSession.mockResolvedValue({
      user: { id: 'test-user-id', email: 'test@example.com' },
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
      const mockPythonResponse: OrchestrationOutput = { // Using the TypeScript OrchestrationOutput for the shape
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

      // Use imported Mock type for assertion
      (fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockPythonResponse,
        status: 200,
      } as Response);

      const requestBody = { source_url: sourceUrl };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(200);
      expect(fetch).toHaveBeenCalledTimes(1); // Check global.fetch directly
      expect(fetch).toHaveBeenCalledWith(
        `${process.env.AISERVICE_URL}/reconstruct-and-analyze`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            source_identifier: sourceUrl,
            source_type: 'url',
            user_id: 'test-user-id',
            job_id: expect.any(String), // job_id is generated in the route
          }),
        })
      );

      // As per the route's logic, it maps pythonServiceResponse to a specific structure
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

      const requestBody = { source_url: 'https://example.com/article' };
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

    it('should return 500 if AISERVICE_URL is not set', async () => {
      delete process.env.AISERVICE_URL; // Or set to undefined

      const requestBody = { source_url: 'https://example.com/article' };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(500);
      expect(responseBody).toEqual({ error: 'AI service configuration error.' });
      expect(fetch).not.toHaveBeenCalled();
    });

    it('should return 400 if both source_url and file_id are missing', async () => {
      const requestBody = {}; // Empty body
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(400);
      expect(responseBody).toEqual({
        error: 'Invalid request body: source_url or file_id is required.',
      });
      expect(fetch).not.toHaveBeenCalled();
    });
    
    it('should return 400 if both source_url and file_id are provided', async () => {
      const requestBody = { source_url: 'https://example.com/article', file_id: 'some-file-id' };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(400);
      expect(responseBody).toEqual({
        error: 'Invalid request body: provide either source_url or file_id, not both.',
      });
      expect(fetch).not.toHaveBeenCalled();
    });

    it('should handle Python service error (500) with JSON response', async () => {
      const sourceUrl = 'https://example.com/article-causing-error';
      const pythonErrorResponse = { 
        message: 'Python internal server error', 
        code: 'PYTHON_ERROR_XYZ' 
      };
      const jobIdUsedByRoute = expect.getState().currentTestName; // Just a placeholder, job_id is uuid

      (fetch as Mock).mockResolvedValueOnce({
        ok: false, // Important: !response.ok
        json: async () => pythonErrorResponse,
        status: 500,
        statusText: 'Internal Server Error',
      } as Response);

      const requestBody = { source_url: sourceUrl };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(500);
      expect(fetch).toHaveBeenCalledTimes(1);
      // The Next.js route should return a specific structure for Python service failures
      expect(responseBody).toEqual({
        error: 'Python aiservice failed to reconstruct and analyze content.',
        details: pythonErrorResponse.message, // The route picks up the message field
        reconstruction_id: expect.any(String), // job_id is returned even on failure
      });
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
        url: `${process.env.AISERVICE_URL}/reconstruct-and-analyze`,
        clone: vi.fn(),
        arrayBuffer: vi.fn(),
        blob: vi.fn(),
        formData: vi.fn(),
        body: null,
        bodyUsed: false,
      } as unknown as Response);

      const requestBody = { source_url: sourceUrl };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(502); // Status code from Python service is passed through
      expect(responseBody).toEqual({
        error: 'Python aiservice failed to reconstruct and analyze content.',
        details: pythonErrorText,
        reconstruction_id: expect.any(String),
      });
    });

    it('should handle network error when fetching from Python service', async () => {
      const sourceUrl = 'https://example.com/article-network-error';
      
      (fetch as Mock).mockRejectedValueOnce(new TypeError('fetch failed')); // Simulate network error

      const requestBody = { source_url: sourceUrl };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(503); // Service Unavailable due to fetch failure
      expect(responseBody).toEqual({
        error: 'Failed to connect to Python aiservice.',
        details: 'fetch failed',
      });
    });

    it('should successfully reconstruct content from a File ID and return the mapped OrchestrationOutput', async () => {
      const fileId = 'test-file-id-xyz789';
      const mockPythonResponse: OrchestrationOutput = {
        document_id: 'python-doc-id-456',
        user_id: 'test-user-id',
        status_code: 'success',
        source_identifier: fileId, // Python service would receive and might return the file_id as source_identifier
        source_type: 'file', // Expected source_type
        processing_level_used: 'full_content',
        extracted_title: 'Test File Document Title',
        is_long_article: true, // Let's make this one long
        original_content_blocks: [{ block_id: 'fb1', type: 'text', text_content: 'Content from file.' }],
        processed_images_data: {},
        document_metadata: { original_title: 'Test File Document Title', source_url: undefined }, // Use undefined instead of null
        error_message: null, // error_message in OrchestrationOutput is Optional<str> in Python, so string | null | undefined is fine here
      };

      (fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockPythonResponse,
        status: 200,
      } as Response);

      const requestBody = { file_id: fileId };
      const req = new NextRequest(`http://localhost/api/ai/reconstruct-and-analyze`, {
        method: 'POST',
        body: JSON.stringify(requestBody),
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await POST(req);
      const responseBody = await response.json();

      expect(response.status).toBe(200);
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(fetch).toHaveBeenCalledWith(
        `${process.env.AISERVICE_URL}/reconstruct-and-analyze`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            source_identifier: fileId,
            source_type: 'file', // Crucial check for file_id input
            user_id: 'test-user-id',
            job_id: expect.any(String),
          }),
        })
      );

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

    // More test cases will be added here:
    // - Success (File ID)
    // - Python Service Non-JSON Error // This is covered by the one above
    // - Network error when calling Python service // Covered
    // - Invalid input (Next.js validation: missing source_url and file_id) // Covered
    // - Unauthorized (getServerSession returns null) // Covered
    // - AISERVICE_URL not set // Covered
  });
}); 