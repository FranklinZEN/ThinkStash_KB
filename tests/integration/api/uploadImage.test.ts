import { POST } from '@/app/api/upload/image/route';
// import { getServerSession } from 'next-auth/next'; // Original import
import { NextRequest } from 'next/server';
import { mockDeep, mockReset } from 'jest-mock-extended';

// --- Mock next-auth/next --- START ---
const mockGetServerSession = jest.fn();
jest.mock('next-auth/next', () => ({
  __esModule: true,
  getServerSession: mockGetServerSession,
}));
// --- Mock next-auth/next --- END ---

// Mock next/headers
jest.mock('next/headers', () => ({
  __esModule: true,
  headers: jest.fn(() => {
    // Try to use global.Headers if available, otherwise fall back to a detailed mock
    const mockCookieString = 'next-auth.session-token=mock-session-token; other-cookie=value';
    let headersInstance;
    try {
      headersInstance = new Headers(); // Use native Headers
      headersInstance.set('cookie', mockCookieString);
    } catch (e) {
      // Fallback if native Headers are not available or constructor fails
      const MOCK_NEXT_HEADERS_SYMBOL = Symbol.for('NextInternalHeaders');
      headersInstance = {
        [MOCK_NEXT_HEADERS_SYMBOL]: true,
        entries: () => [
          ['cookie', mockCookieString]
        ] as IterableIterator<[string, string]>, // Explicitly type as iterable of pairs
        forEach: (callback: (value: string, key: string, parent: any) => void) => {
          const headerMap = new Map([['cookie', mockCookieString]]);
          headerMap.forEach((value, key) => callback(value, key, headerMap));
        },
        get: (name: string) => (name.toLowerCase() === 'cookie' ? mockCookieString : null),
        has: (name: string) => name.toLowerCase() === 'cookie',
        append: jest.fn(),
        delete: jest.fn(),
        set: jest.fn(),
        getAll: (name: string) => (name.toLowerCase() === 'cookie' ? [mockCookieString] : []),
      };
    }
    return headersInstance as any;
  }),
  cookies: jest.fn(() => {
    const cookieStore = new Map<string, { name: string; value: string }>();
    const mockSessionTokenCookieName = 'next-auth.session-token'; // Or your actual session token name
    const mockSessionTokenValue = 'mock-session-token-value';
    cookieStore.set(mockSessionTokenCookieName, { name: mockSessionTokenCookieName, value: mockSessionTokenValue });
    
    // Add another cookie for getAll testing if necessary
    // cookieStore.set('another-cookie', { name: 'another-cookie', value: 'another-value' });

    return {
      get: jest.fn((name: string) => cookieStore.get(name)),
      getAll: jest.fn(() => Array.from(cookieStore.values())), // Returns array of {name, value} objects
      set: jest.fn((name: string, value: string) => cookieStore.set(name, { name, value })),
      // Add other methods like 'has', 'delete' if your auth setup or tests use them
    };
  }),
}));

// --- Mock lib/gcs --- START ---
// Storing mock functions at a higher scope to be accessible in beforeEach/tests
const gcsLibMocks = {
  uploadBufferToGCS: jest.fn(),
  getGCSFileStream: jest.fn(),
  deleteGCSFile: jest.fn(),
};
jest.mock('@lib/gcs', () => ({
  __esModule: true,
  uploadBufferToGCS: gcsLibMocks.uploadBufferToGCS,
  getGCSFileStream: gcsLibMocks.getGCSFileStream, 
  deleteGCSFile: gcsLibMocks.deleteGCSFile,     
  bucketName: 'mock-bucket-from-upload-test' 
}));
// --- Mock lib/gcs --- END ---

// Mock uuid
jest.mock('uuid', () => ({
  v4: () => 'test-uuid',
}));

describe('/api/upload/image', () => {
  beforeEach(() => {
    mockGetServerSession.mockReset();
    
    // Reset GCS mocks from gcsLibMocks
    gcsLibMocks.uploadBufferToGCS.mockReset();
    gcsLibMocks.getGCSFileStream.mockReset();
    gcsLibMocks.deleteGCSFile.mockReset();
  });

  describe('POST', () => {
    it('should successfully upload an image and return metadata', async () => {
      // Arrange
      const mockUserId = 'user-123';
      mockGetServerSession.mockResolvedValue({ // This should now be the only thing getServerSession does
        user: { id: mockUserId, email: 'test@example.com' },
      });

      const mockFile = new File(['dummy content'], 'test-image.png', { type: 'image/png' });
      const formData = new FormData();
      formData.append('file', mockFile);

      const request = mockDeep<NextRequest>();
      (request.formData as jest.Mock).mockResolvedValue(formData); // Ensure formData is a mock if using mockDeep
      
      const expectedGcsPathForMock = `images/${mockUserId}/test-uuid.png`; // Corrected based on uuid mock
      gcsLibMocks.uploadBufferToGCS.mockResolvedValue(expectedGcsPathForMock);

      // Act
      const response = await POST(request);
      const body = await response.json();

      // Assert
      expect(response.status).toBe(200);
      expect(body).toEqual({
        // url: `/api/images/images/${mockUserId}/test-uuid.png`, // old, based on previous mock
        appServedUrl: `/api/images/images/${mockUserId}/test-uuid.png`, // Updated to appServedUrl
        gcsPath: `images/${mockUserId}/test-uuid.png`,
        contentType: 'image/png',
        originalFilename: 'test-image.png',
        size: mockFile.size,
        userId: mockUserId, // Ensure userId is in the response as per UploadApiResponse
      });
      expect(gcsLibMocks.uploadBufferToGCS).toHaveBeenCalledTimes(1);
      expect(gcsLibMocks.uploadBufferToGCS).toHaveBeenCalledWith(
        expect.any(Buffer),
        `images/${mockUserId}/test-uuid.png`, // Corrected based on uuid mock
        'image/png' // content type is passed to GCS service in this version
      );
    });

    it('should return 401 if user is not authenticated', async () => {
      mockGetServerSession.mockResolvedValue(null); // Ensures getServerSession returns null
      const formData = new FormData();
      formData.append('file', new File(['content'], 'test.png', {type: 'image/png'}));
      const request = mockDeep<NextRequest>();
      (request.formData as jest.Mock).mockResolvedValue(formData);
      const response = await POST(request);
      const body = await response.json();
      expect(response.status).toBe(401);
      expect(body.error).toBe('Unauthorized');
      expect(gcsLibMocks.uploadBufferToGCS).not.toHaveBeenCalled();
    });

    it('should return 400 if no file is provided', async () => {
      mockGetServerSession.mockResolvedValue({ user: { id: 'user-123' } }); // Authenticated
      const formData = new FormData(); // Empty formData
      const request = mockDeep<NextRequest>();
      (request.formData as jest.Mock).mockResolvedValue(formData);
      const response = await POST(request);
      const body = await response.json();
      expect(response.status).toBe(400);
      expect(body.error).toBe('No file provided.');
      expect(gcsLibMocks.uploadBufferToGCS).not.toHaveBeenCalled();
    });

    it('should return 400 for invalid file type', async () => {
      mockGetServerSession.mockResolvedValue({ user: { id: 'user-123' } });
      const mockFile = new File(['dummy content'], 'test-document.txt', { type: 'text/plain' });
      const formData = new FormData();
      formData.append('file', mockFile);
      const request = mockDeep<NextRequest>();
      request.formData.mockResolvedValue(formData);
      const response = await POST(request);
      const body = await response.json();
      expect(response.status).toBe(400);
      expect(body.error).toContain('Invalid file type');
      expect(gcsLibMocks.uploadBufferToGCS).not.toHaveBeenCalled();
    });

    it('should return 400 if file size exceeds maximum', async () => {
      mockGetServerSession.mockResolvedValue({ user: { id: 'user-123' } });
      const largeBuffer = Buffer.alloc(5 * 1024 * 1024 + 1); 
      const mockFile = new File([largeBuffer], 'large-image.png', { type: 'image/png' });
      const formData = new FormData();
      formData.append('file', mockFile);
      const request = mockDeep<NextRequest>();
      request.formData.mockResolvedValue(formData);
      const response = await POST(request);
      const body = await response.json();
      expect(response.status).toBe(400);
      expect(body.error).toContain('File exceeds maximum size');
      expect(gcsLibMocks.uploadBufferToGCS).not.toHaveBeenCalled();
    });

    it('should return 500 if GCS upload fails (simulated)', async () => {
      mockGetServerSession.mockResolvedValue({ user: { id: 'user-123' } });
      const mockFile = new File(['dummy content'], 'test-image.png', { type: 'image/png' });
      const formData = new FormData();
      formData.append('file', mockFile);
      const request = mockDeep<NextRequest>();
      (request.formData as jest.Mock).mockResolvedValue(formData);

      gcsLibMocks.uploadBufferToGCS.mockRejectedValue(new Error('GCS Upload Kaboom'));

      const response = await POST(request);
      const body = await response.json();
      expect(response.status).toBe(500);
      expect(body.error).toBe('Image upload failed');
      expect(body.details).toBe('GCS Upload Kaboom');
    });
  });
}); 