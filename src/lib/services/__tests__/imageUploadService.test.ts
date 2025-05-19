import {
  handleImageUploadLogic,
  ImageUploadInput,
  ImageRecordPrismaSubset,
} from '../imageUploadService';
import { uploadFile } from '@/lib/gcs';
// No import of prisma from '@/lib/prisma' needed here anymore

jest.mock('@/lib/gcs', () => ({
  // Mock GCS
  uploadFile: jest.fn(),
}));

const mockUploadFile = uploadFile as jest.Mock;

// Create standalone mock functions for Prisma operations
const mockPrismaImageRecordCreateFn = jest.fn();
const mockPrismaImageRecordUpdateFn = jest.fn();

// Create the mock Prisma subset object to be passed to the service
const mockPrismaInstance: ImageRecordPrismaSubset = {
  imageRecord: {
    create: mockPrismaImageRecordCreateFn,
    update: mockPrismaImageRecordUpdateFn,
  },
  // $transaction: jest.fn(), // Add if your service interface requires it
};

const MOCK_USER_ID = 'user-123';
const MOCK_FILE_BUFFER = Buffer.from('test-image-content');

const createMockInput = (
  overrides: Partial<ImageUploadInput> = {},
): ImageUploadInput => ({
  userId: MOCK_USER_ID,
  fileBuffer: MOCK_FILE_BUFFER,
  originalFilename: 'test.jpg',
  contentType: 'image/jpeg',
  fileSize: 1024 * 100, // 100KB
  ...overrides,
});

describe('handleImageUploadLogic', () => {
  beforeEach(() => {
    mockPrismaImageRecordCreateFn.mockReset();
    mockPrismaImageRecordUpdateFn.mockReset();
    mockUploadFile.mockReset();
    // if (mockPrismaInstance.$transaction) (mockPrismaInstance.$transaction as jest.Mock).mockClear();
  });

  describe('Validations', () => {
    it('should return 400 for invalid MIME type', async () => {
      const input = createMockInput({ contentType: 'application/pdf' });
      const result = await handleImageUploadLogic(input, mockPrismaInstance); // Pass mock
      expect(result.success).toBe(false);
      expect(result.status).toBe(400);
      expect(result.error).toContain('Invalid file type');
    });

    it('should return 400 if file size exceeds limit', async () => {
      const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
      const input = createMockInput({ fileSize: MAX_FILE_SIZE_BYTES + 1 });
      const result = await handleImageUploadLogic(input, mockPrismaInstance); // Pass mock
      expect(result.success).toBe(false);
      expect(result.status).toBe(400);
      expect(result.error).toContain('exceeds maximum size');
    });
  });

  describe('Successful Upload', () => {
    const mockGcsFilename = `${MOCK_USER_ID}/gcs-file.jpg`;
    const mockImageRecordId = 'cuid-for-image-record';
    const input = createMockInput();

    beforeEach(() => {
      mockUploadFile.mockResolvedValue({
        filename: mockGcsFilename,
        url: 'mock-gcs-signed-url',
      });
      mockPrismaImageRecordCreateFn.mockResolvedValue({
        id: mockImageRecordId,
        userId: input.userId,
        gcsPath: mockGcsFilename,
        contentType: input.contentType,
        originalFilename: input.originalFilename,
        size: input.fileSize,
        appServedUrl: '',
        knowledgeCardId: null,
        createdAt: new Date(),
        updatedAt: new Date(),
      });
      mockPrismaImageRecordUpdateFn.mockResolvedValue({
        id: mockImageRecordId,
        appServedUrl: `/api/images/serve/${mockImageRecordId}`,
      });
    });

    it('should call GCS upload, create and update ImageRecord, and return success with URLs', async () => {
      const result = await handleImageUploadLogic(input, mockPrismaInstance); // Pass mock

      expect(mockUploadFile).toHaveBeenCalledWith(
        input.fileBuffer,
        input.originalFilename,
        input.contentType,
      );
      expect(mockPrismaImageRecordCreateFn).toHaveBeenCalledWith({
        data: {
          userId: input.userId,
          gcsPath: mockGcsFilename,
          contentType: input.contentType,
          originalFilename: input.originalFilename,
          size: input.fileSize,
          appServedUrl: '',
        },
        select: {
          id: true,
          userId: true,
          gcsPath: true,
          contentType: true,
          originalFilename: true,
          size: true,
          appServedUrl: true,
          knowledgeCardId: true,
          createdAt: true,
          updatedAt: true,
        },
      });
      expect(mockPrismaImageRecordUpdateFn).toHaveBeenCalledWith({
        where: { id: mockImageRecordId },
        data: { appServedUrl: `/api/images/serve/${mockImageRecordId}` },
        select: { id: true, appServedUrl: true },
      });
      expect(result.success).toBe(true);
      expect(result.imageRecordId).toBe(mockImageRecordId);
      expect(result.appServedUrl).toBe(
        `/api/images/serve/${mockImageRecordId}`,
      );
      expect(result.status).toBe(200);
    });
  });

  describe('Failure Scenarios', () => {
    it('should return 500 if GCS upload fails', async () => {
      mockUploadFile.mockRejectedValue(new Error('GCS Upload Error'));
      const input = createMockInput();
      const result = await handleImageUploadLogic(input, mockPrismaInstance); // Pass mock
      expect(result.success).toBe(false);
      expect(result.status).toBe(500);
      expect(result.error).toContain('GCS operation failed');
      expect(result.details).toBe('GCS Upload Error');
      expect(mockPrismaImageRecordCreateFn).not.toHaveBeenCalled();
    });

    it('should return 500 if Prisma create fails', async () => {
      mockUploadFile.mockResolvedValue({
        filename: 'test/gcs-for-create-fail.jpg',
        url: 'mock-url',
      });
      mockPrismaImageRecordCreateFn.mockRejectedValue(
        new Error('Prisma Create Error'),
      );

      const input = createMockInput();
      const result = await handleImageUploadLogic(input, mockPrismaInstance);

      expect(result.success).toBe(false);
      expect(result.status).toBe(500);
      expect(result.error).toBe('Prisma Create Error');
      expect(result.details).toBeUndefined();
      expect(mockPrismaImageRecordUpdateFn).not.toHaveBeenCalled();
    });

    it('should return 500 if Prisma update fails', async () => {
      mockUploadFile.mockResolvedValue({
        filename: 'test/gcs-for-update-fail.jpg',
        url: 'mock-url',
      });
      mockPrismaImageRecordCreateFn.mockResolvedValue({
        id: 'temp-id',
        userId: MOCK_USER_ID,
        gcsPath: 'path',
        contentType: 'type',
        originalFilename: 'name',
        size: 100,
        appServedUrl: '',
        knowledgeCardId: null,
        createdAt: new Date(),
        updatedAt: new Date(),
      });
      mockPrismaImageRecordUpdateFn.mockRejectedValue(
        new Error('Prisma Update Error'),
      );

      const input = createMockInput();
      const result = await handleImageUploadLogic(input, mockPrismaInstance);

      expect(result.success).toBe(false);
      expect(result.status).toBe(500);
      expect(result.error).toBe('Prisma Update Error');
      expect(result.details).toBeUndefined();
    });
  });
});
