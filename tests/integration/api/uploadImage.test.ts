import { POST } from '@/app/api/upload/image/route';
import { getServerSession } from 'next-auth';
// We will get the mocked functions via require later
// import * as GCSService from '@lib/gcs'; 
import { NextRequest } from 'next/server';
import { mockDeep, mockReset } from 'jest-mock-extended';

// Mock next-auth
jest.mock('next-auth');
const mockGetServerSession = getServerSession as jest.Mock;

// Mock lib/gcs
jest.mock('@lib/gcs', () => ({
  __esModule: true,
  uploadBufferToGCS: jest.fn(), // Define mocks inside the factory
  getGCSFileStream: jest.fn(), 
  deleteGCSFile: jest.fn(),     
  bucketName: 'mock-bucket-from-upload-test' 
}));

// Mock uuid
jest.mock('uuid', () => ({
  v4: () => 'test-uuid',
}));

describe('/api/upload/image', () => {
  let mockUploadBufferToGCSFn: jest.Mock; // To hold the mock function for use in tests

  beforeEach(() => {
    // Get the mocked functions from the module Jest is using
    const gcsMock = require('@lib/gcs');
    mockUploadBufferToGCSFn = gcsMock.uploadBufferToGCS;
    
    mockGetServerSession.mockReset();
    mockUploadBufferToGCSFn.mockReset();
    // If other GCS functions were used by SUT, get and reset them too:
    // gcsMock.getGCSFileStream.mockReset();
    // gcsMock.deleteGCSFile.mockReset();
  });

  describe('POST', () => {
    it('should successfully upload an image and return metadata', async () => {
      // Arrange
      const mockUserId = 'user-123';
      mockGetServerSession.mockResolvedValue({
        user: { id: mockUserId, email: 'test@example.com' },
      });

      const mockFile = new File(['dummy content'], 'test-image.png', { type: 'image/png' });
      const formData = new FormData();
      formData.append('file', mockFile);

      const request = mockDeep<NextRequest>();
      request.formData.mockResolvedValue(formData);
      
      const expectedGcsPathForMock = `images/${mockUserId}/test-uuid-test-image.png`;
      mockUploadBufferToGCSFn.mockResolvedValue(expectedGcsPathForMock);

      // Act
      const response = await POST(request);
      const body = await response.json();

      // Assert
      expect(response.status).toBe(200);
      expect(body).toEqual({
        url: `/api/images/images/${mockUserId}/test-uuid-test-image.png`,
        gcsPath: `images/${mockUserId}/test-uuid-test-image.png`,
        contentType: 'image/png',
        originalFilename: 'test-image.png',
        size: mockFile.size,
      });
      expect(mockUploadBufferToGCSFn).toHaveBeenCalledTimes(1);
      const expectedGcsPath = `images/${mockUserId}/test-uuid-test-image.png`;
      expect(mockUploadBufferToGCSFn).toHaveBeenCalledWith(
        expect.any(Buffer),
        expectedGcsPath,
        'image/png'
      );
    });

    it('should return 401 if user is not authenticated', async () => {
      mockGetServerSession.mockResolvedValue(null);
      const formData = new FormData();
      formData.append('file', new File(['content'], 'test.png', {type: 'image/png'}));
      const request = mockDeep<NextRequest>();
      request.formData.mockResolvedValue(formData);
      const response = await POST(request);
      const body = await response.json();
      expect(response.status).toBe(401);
      expect(body.error).toBe('Unauthorized');
      expect(mockUploadBufferToGCSFn).not.toHaveBeenCalled();
    });

    it('should return 400 if no file is provided', async () => {
      mockGetServerSession.mockResolvedValue({ user: { id: 'user-123' } });
      const formData = new FormData();
      const request = mockDeep<NextRequest>();
      request.formData.mockResolvedValue(formData);
      const response = await POST(request);
      const body = await response.json();
      expect(response.status).toBe(400);
      expect(body.error).toBe('No file provided');
      expect(mockUploadBufferToGCSFn).not.toHaveBeenCalled();
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
      expect(mockUploadBufferToGCSFn).not.toHaveBeenCalled();
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
      expect(mockUploadBufferToGCSFn).not.toHaveBeenCalled();
    });

    // TODO: Add test for GCS upload failure if needed
    // it('should return 500 if GCS upload fails', async () => { ... });
  });
}); 