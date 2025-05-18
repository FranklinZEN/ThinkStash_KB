import { GET } from '@/app/api/images/[...gcsPath]/route';
import { getServerSession } from 'next-auth/next';
import prisma from '@/lib/prisma'; // Jest should automatically use src/lib/__mocks__/prisma.ts
// We do not need to import from '@lib/gcs' if we are mocking @google-cloud/storage directly
import { NextRequest } from 'next/server';
import { Readable } from 'stream';
import { mockDeep, mockReset, DeepMockProxy } from 'jest-mock-extended';

// --- Mock @google-cloud/storage --- START ---
const mockFileExists = jest.fn();
const mockCreateReadStream = jest.fn();
const mockFile = jest.fn(() => ({
  exists: mockFileExists,
  createReadStream: mockCreateReadStream,
}));
const mockBucket = jest.fn(() => ({ file: mockFile }));

jest.mock('@google-cloud/storage', () => ({
  Storage: jest.fn(() => ({
    bucket: mockBucket,
  })),
}));
// --- Mock @google-cloud/storage --- END ---

// Mock next-auth
jest.mock('next-auth/next');
const mockGetServerSession = getServerSession as jest.Mock;

let mockPrismaInTest: DeepMockProxy<typeof prisma>;

describe('/api/images/[...gcsPath]', () => {
  beforeEach(() => {
    mockPrismaInTest = prisma as DeepMockProxy<typeof prisma>;
    mockReset(mockPrismaInTest);
    mockReset(mockGetServerSession);

    // Reset GCS mocks
    mockFileExists.mockReset();
    mockCreateReadStream.mockReset();
    mockFile.mockClear(); // Use mockClear for functions that return other mocks
    mockBucket.mockClear();
    // The Storage constructor mock itself doesn't need reset usually unless its behavior changes per test
  });

  // afterEach can be removed if spies are not used globally or if jest.clearAllMocks() is in setup

  describe('GET', () => {
    const mockRequestingUserId = 'user-authed-123';
    const mockCardOwnerId = 'user-authed-123';
    const mockOtherUserId = 'user-other-456';
    const mockGCSPath = 'images/user-authed-123/test-image.png';
    const mockGCSPathArray = ['images', 'user-authed-123', 'test-image.png'];
    const mockContentType = 'image/png';

    const createMockRequest = () => mockDeep<NextRequest>();

    it('should successfully serve an image for an authenticated and authorized user', async () => {
      mockGetServerSession.mockResolvedValue({ user: { id: mockRequestingUserId } });
      mockPrismaInTest.imageMetadata.findUnique.mockResolvedValue({
        contentType: mockContentType,
        knowledgeCard: { userId: mockCardOwnerId },
        id: 'meta-id', knowledgeCardId: 'card-id', userId: mockCardOwnerId,
        gcsPath: mockGCSPath, originalFilename: 'test-image.png', size: 12345,
        appServedUrl: '/api/images/' + mockGCSPath, createdAt: new Date(), updatedAt: new Date(),
      });
      mockFileExists.mockResolvedValue([true]); // .exists() returns [boolean]
      const mockNodeStream = new Readable({ read() { this.push('image data'); this.push(null); } });
      mockCreateReadStream.mockReturnValue(mockNodeStream);

      const request = createMockRequest();
      const context = { params: { gcsPath: mockGCSPathArray } };
      const response = await GET(request, context);
      expect(response.status).toBe(200);
      expect(response.headers.get('Content-Type')).toBe(mockContentType);
      expect(mockFile).toHaveBeenCalledWith(mockGCSPath);
      expect(mockCreateReadStream).toHaveBeenCalled();
    });

    it('should return 401 if user is not authenticated', async () => {
      mockGetServerSession.mockResolvedValue(null);
      const request = createMockRequest();
      const context = { params: { gcsPath: mockGCSPathArray } };
      const response = await GET(request, context);
      const body = await response.json();
      expect(response.status).toBe(401);
      expect(body.error).toBe('Unauthorized');
      expect(mockPrismaInTest.imageMetadata.findUnique).not.toHaveBeenCalled();
      expect(mockCreateReadStream).not.toHaveBeenCalled();
    });

    it('should return 403 if user is authenticated but not authorized (different owner)', async () => {
      mockGetServerSession.mockResolvedValue({ user: { id: mockOtherUserId } });
      mockPrismaInTest.imageMetadata.findUnique.mockResolvedValue({
        contentType: mockContentType,
        knowledgeCard: { userId: mockCardOwnerId }, 
        id: 'meta-id', knowledgeCardId: 'card-id', userId: mockCardOwnerId,
        gcsPath: mockGCSPath, originalFilename: 'test-image.png', size: 12345,
        appServedUrl: '/api/images/' + mockGCSPath, createdAt: new Date(), updatedAt: new Date(),
      });
      const request = createMockRequest();
      const context = { params: { gcsPath: mockGCSPathArray } };
      const response = await GET(request, context);
      const body = await response.json();
      expect(response.status).toBe(403);
      expect(body.error).toBe('Forbidden');
      expect(mockPrismaInTest.imageMetadata.findUnique).toHaveBeenCalledWith({ 
        where: { gcsPath: mockGCSPath }, 
        include: { knowledgeCard: { select: { userId: true } } } 
      });
      expect(mockCreateReadStream).not.toHaveBeenCalled();
    });

    it('should return 404 if ImageMetadata is not found', async () => {
      mockGetServerSession.mockResolvedValue({ user: { id: mockRequestingUserId } });
      mockPrismaInTest.imageMetadata.findUnique.mockResolvedValue(null);
      const request = createMockRequest();
      const context = { params: { gcsPath: mockGCSPathArray } };
      const response = await GET(request, context);
      const body = await response.json();
      expect(response.status).toBe(404);
      expect(body.error).toBe('Image not found.');
      expect(mockCreateReadStream).not.toHaveBeenCalled();
    });

    it('should return 404 if GCS file does not exist (file.exists() is false)', async () => {
      mockGetServerSession.mockResolvedValue({ user: { id: mockRequestingUserId } });
      mockPrismaInTest.imageMetadata.findUnique.mockResolvedValue({
        contentType: mockContentType,
        knowledgeCard: { userId: mockCardOwnerId },
         id: 'meta-id', knowledgeCardId: 'card-id', userId: mockCardOwnerId,
        gcsPath: mockGCSPath, originalFilename: 'test-image.png', size: 12345,
        appServedUrl: '/api/images/' + mockGCSPath, createdAt: new Date(), updatedAt: new Date(),
      });
      mockFileExists.mockResolvedValue([false]); // Simulate GCS file not existing     
      const request = createMockRequest();
      const context = { params: { gcsPath: mockGCSPathArray } };
      const response = await GET(request, context);
      const body = await response.json();
      expect(response.status).toBe(404);
      expect(body.error).toBe('File not found in storage.'); 
      expect(mockCreateReadStream).not.toHaveBeenCalled();
    });

    it('should return 400 if gcsPath parameter is missing or empty', async () => {
      mockGetServerSession.mockResolvedValue({ user: { id: mockRequestingUserId } });
      const request = createMockRequest();
      const context = { params: { gcsPath: [] } }; 
      const response = await GET(request, context);
      const body = await response.json();
      expect(response.status).toBe(400);
      expect(body.error).toBe('Image path not provided.');
    });
  });
}); 