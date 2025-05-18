import { GET } from '@/app/api/images/[...gcsPath]/route';
import { getServerSession } from 'next-auth/next';
import prisma from '@/lib/prisma'; // Jest should automatically use src/lib/__mocks__/prisma.ts
import * as GCSService from '@/lib/gcs';
import { NextRequest } from 'next/server';
import { Readable } from 'stream';
import { mockReset, DeepMockProxy } from 'jest-mock-extended'; // mockDeep is in the __mocks__ file

// Mock next-auth
jest.mock('next-auth/next');
const mockGetServerSession = getServerSession as jest.Mock;

// Mock @lib/gcs (factory pattern)
const mockGetGCSFileStreamFn = jest.fn();
const mockUploadBufferToGCSFn_serve = jest.fn(); 
const mockDeleteGCSFileFn_serve = jest.fn();
jest.mock('@lib/gcs', () => ({
    __esModule: true,
    getGCSFileStream: mockGetGCSFileStreamFn,
    uploadBufferToGCS: mockUploadBufferToGCSFn_serve,
    deleteGCSFile: mockDeleteGCSFileFn_serve,
    bucketName: 'mock-bucket-for-serve-image-test'
}));

// REMOVED explicit jest.mock('@/lib/prisma', ...)
// Manual mock src/lib/__mocks__/prisma.ts should be used.

let mockPrismaInTest: DeepMockProxy<typeof prisma>; // Type with the imported prisma (which is mocked)


describe('/api/images/[...gcsPath]', () => {
  beforeEach(() => {
    // prisma is now the deep mock instance from the __mocks__ directory
    mockPrismaInTest = prisma as DeepMockProxy<typeof prisma>; 
    mockReset(mockPrismaInTest);

    mockReset(mockGetServerSession);
    mockGetGCSFileStreamFn.mockReset();
    mockUploadBufferToGCSFn_serve.mockReset();
    mockDeleteGCSFileFn_serve.mockReset();
  });

  describe('GET', () => {
    const mockRequestingUserId = 'user-authed-123';
    const mockCardOwnerId = 'user-authed-123';
    const mockOtherUserId = 'user-other-456';
    const mockGCSPath = 'images/user-authed-123/test-image.png';
    const mockGCSPathArray = ['images', 'user-authed-123', 'test-image.png'];
    const mockContentType = 'image/png';

    // Helper to create a NextRequest mock
    const createMockRequest = () => mockDeep<NextRequest>();

    it('should successfully serve an image for an authenticated and authorized user', async () => {
      // Arrange
      mockGetServerSession.mockResolvedValue({ user: { id: mockRequestingUserId } });
      mockPrismaInTest.imageMetadata.findUnique.mockResolvedValue({
        contentType: mockContentType,
        knowledgeCard: { userId: mockCardOwnerId },
        id: 'meta-id',
        knowledgeCardId: 'card-id',
        userId: mockCardOwnerId,
        gcsPath: mockGCSPath,
        originalFilename: 'test-image.png',
        size: 12345,
        appServedUrl: '/api/images/' + mockGCSPath,
        createdAt: new Date(),
        updatedAt: new Date(),
      });
      const mockStream = new Readable({ read() { this.push('image data'); this.push(null); } });
      mockGetGCSFileStreamFn.mockResolvedValue(mockStream);

      const request = createMockRequest();
      const context = { params: { gcsPath: mockGCSPathArray } };

      // Act
      const response = await GET_serveImage(request, context);
      // const responseBody = await response.text(); // Reading stream consumes it

      // Assert
      expect(response.status).toBe(200);
      expect(response.headers.get('Content-Type')).toBe(mockContentType);
      expect(mockGetGCSFileStreamFn).toHaveBeenCalledWith(mockGCSPath);
      // expect(responseBody).toBe('image data'); // Uncomment if you want to verify stream content
    });

    it('should return 401 if user is not authenticated', async () => {
      // Arrange
      mockGetServerSession.mockResolvedValue(null);
      const request = createMockRequest();
      const context = { params: { gcsPath: mockGCSPathArray } };

      // Act
      const response = await GET_serveImage(request, context);
      const body = await response.json();

      // Assert
      expect(response.status).toBe(401);
      expect(body.error).toBe('Unauthorized');
      expect(mockPrismaInTest.imageMetadata.findUnique).not.toHaveBeenCalled();
      expect(mockGetGCSFileStreamFn).not.toHaveBeenCalled();
    });

    it('should return 403 if user is authenticated but not authorized (different owner)', async () => {
      // Arrange
      mockGetServerSession.mockResolvedValue({ user: { id: mockOtherUserId } }); // Requesting user is different
      mockPrismaInTest.imageMetadata.findUnique.mockResolvedValue({
        contentType: mockContentType,
        knowledgeCard: { userId: mockCardOwnerId }, // Card owner is mockCardOwnerId
        id: 'meta-id', knowledgeCardId: 'card-id', userId: mockCardOwnerId,
        gcsPath: mockGCSPath, originalFilename: 'test-image.png', size: 12345,
        appServedUrl: '/api/images/' + mockGCSPath, createdAt: new Date(), updatedAt: new Date(),
      });

      const request = createMockRequest();
      const context = { params: { gcsPath: mockGCSPathArray } };

      // Act
      const response = await GET_serveImage(request, context);
      const body = await response.json();

      // Assert
      expect(response.status).toBe(403);
      expect(body.error).toBe('Forbidden');
      expect(mockPrismaInTest.imageMetadata.findUnique).toHaveBeenCalledWith({ where: { gcsPath: mockGCSPath }, select: expect.any(Object) });
      expect(mockGetGCSFileStreamFn).not.toHaveBeenCalled();
    });

    it('should return 404 if ImageMetadata is not found', async () => {
      // Arrange
      mockGetServerSession.mockResolvedValue({ user: { id: mockRequestingUserId } });
      mockPrismaInTest.imageMetadata.findUnique.mockResolvedValue(null); // Simulate metadata not found

      const request = createMockRequest();
      const context = { params: { gcsPath: mockGCSPathArray } };

      // Act
      const response = await GET_serveImage(request, context);
      const body = await response.json();

      // Assert
      expect(response.status).toBe(404);
      expect(body.error).toBe('File not found');
      expect(mockGetGCSFileStreamFn).not.toHaveBeenCalled();
    });

    it('should return 404 if GCS file stream is null (file not in GCS)', async () => {
      // Arrange
      mockGetServerSession.mockResolvedValue({ user: { id: mockRequestingUserId } });
      mockPrismaInTest.imageMetadata.findUnique.mockResolvedValue({
        contentType: mockContentType,
        knowledgeCard: { userId: mockCardOwnerId },
         id: 'meta-id', knowledgeCardId: 'card-id', userId: mockCardOwnerId,
        gcsPath: mockGCSPath, originalFilename: 'test-image.png', size: 12345,
        appServedUrl: '/api/images/' + mockGCSPath, createdAt: new Date(), updatedAt: new Date(),
      });
      mockGetGCSFileStreamFn.mockResolvedValue(null); // Simulate GCS file not found

      const request = createMockRequest();
      const context = { params: { gcsPath: mockGCSPathArray } };

      // Act
      const response = await GET_serveImage(request, context);
      const body = await response.json();

      // Assert
      expect(response.status).toBe(404);
      expect(body.error).toBe('File not found in storage backend');
    });

     it('should return 400 if gcsPath parameter is missing or empty', async () => {
      // Arrange
      mockGetServerSession.mockResolvedValue({ user: { id: mockRequestingUserId } });
      const request = createMockRequest();
      const context = { params: { gcsPath: [] } }; // Empty gcsPath array

      // Act
      const response = await GET_serveImage(request, context);
      const body = await response.json();

      // Assert
      expect(response.status).toBe(400);
      expect(body.error).toBe('File path is required');
    });

  });
}); 