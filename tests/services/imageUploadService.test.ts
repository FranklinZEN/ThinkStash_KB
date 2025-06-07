/**
 * @vitest-environment node
 */
import {
  handleImageUploadLogic,
  ImageUploadInput,
} from '@/lib/services/imageUploadService';
import { uploadFile } from '@/lib/gcs';
import { vi } from 'vitest';

vi.mock('@/lib/gcs', () => ({
  uploadFile: vi.fn(),
}));
const mockUploadFile = uploadFile as ReturnType<typeof vi.fn>;

import {
  mockImageRecordCreate,
  mockImageRecordUpdate,
} from '@/tests/helpers/apiTestSetup';

const MOCK_USER_ID = 'user-123';
const MOCK_FILE_BUFFER = Buffer.from('test-image-content');

const createMockInput = (
  overrides: Partial<ImageUploadInput> = {},
): ImageUploadInput => ({
  userId: MOCK_USER_ID,
  fileBuffer: MOCK_FILE_BUFFER,
  originalFilename: 'test.jpg',
  contentType: 'image/jpeg',
  fileSize: 1024 * 100, 
  ...overrides,
});

describe('handleImageUploadLogic', () => {
  beforeEach(() => {
    mockImageRecordCreate.mockReset();
    mockImageRecordUpdate.mockReset();
    mockUploadFile.mockReset();
  });

  describe('Validations', () => {
    it('should return 400 for invalid MIME type', async () => {
      const input = createMockInput({ contentType: 'application/pdf' });
      const result = await handleImageUploadLogic(input);
      expect(result.success).toBe(false);
      expect(result.status).toBe(400);
      expect(result.error).toContain('Invalid file type');
    });

    it('should return 400 if file size exceeds limit', async () => {
      const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
      const input = createMockInput({ fileSize: MAX_FILE_SIZE_BYTES + 1 });
      const result = await handleImageUploadLogic(input);
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
      mockUploadFile.mockResolvedValue({ filename: mockGcsFilename, url: 'mock-gcs-signed-url' });
      mockImageRecordCreate.mockResolvedValue({
        id: mockImageRecordId, userId: input.userId, gcsPath: mockGcsFilename,
        contentType: input.contentType, originalFilename: input.originalFilename,
        size: input.fileSize, appServedUrl: '', knowledgeCardId: null,
        createdAt: new Date(), updatedAt: new Date(),
      });
      mockImageRecordUpdate.mockResolvedValue({
        id: mockImageRecordId, appServedUrl: `/api/images/serve/${mockImageRecordId}`,
      });
    });

    it('should call GCS upload, create and update ImageRecord, and return success with URLs', async () => {
      const result = await handleImageUploadLogic(input);
      expect(mockUploadFile).toHaveBeenCalledWith(input.fileBuffer, input.originalFilename, input.contentType);
      expect(mockImageRecordCreate).toHaveBeenCalledWith({
        data: {
          userId: input.userId,
          gcsPath: mockGcsFilename,
          contentType: input.contentType,
          originalFilename: input.originalFilename,
          size: input.fileSize,
          appServedUrl: '',
        },
        select: { 
          id: true, userId: true, gcsPath: true, contentType: true, 
          originalFilename: true, size: true, appServedUrl: true, 
          knowledgeCardId: true, createdAt: true, updatedAt: true 
        },
      });
      expect(mockImageRecordUpdate).toHaveBeenCalledWith({
        where: { id: mockImageRecordId }, data: { appServedUrl: `/api/images/serve/${mockImageRecordId}` },
        select: { id: true, appServedUrl: true },
      });
      expect(result.success).toBe(true);
      expect(result.imageRecordId).toBe(mockImageRecordId);
      expect(result.appServedUrl).toBe(`/api/images/serve/${mockImageRecordId}`);
      expect(result.status).toBe(200);
    });
  });

  describe('Failure Scenarios', () => {
    it('should return 500 if GCS upload fails', async () => {
      mockUploadFile.mockRejectedValue(new Error('GCS Upload Error'));
      const input = createMockInput();
      const result = await handleImageUploadLogic(input);
      expect(result.success).toBe(false);
      expect(result.status).toBe(500);
      expect(result.error).toContain('GCS operation failed');
      expect(result.details).toBe('GCS Upload Error');
      expect(mockImageRecordCreate).not.toHaveBeenCalled();
    });

    it('should return 500 if Prisma create fails', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'test/gcs-for-create-fail.jpg', url: 'mock-url' });
      mockImageRecordCreate.mockRejectedValue(new Error('Prisma Create Error'));
      const input = createMockInput();
      const result = await handleImageUploadLogic(input);
      expect(result.success).toBe(false);
      expect(result.status).toBe(500);
      expect(result.error).toBe('Prisma Create Error'); 
      expect(result.details).toBeUndefined(); 
      expect(mockImageRecordUpdate).not.toHaveBeenCalled();
    });

    it('should return 500 if Prisma update fails', async () => {
      mockUploadFile.mockResolvedValue({ filename: 'test/gcs-for-update-fail.jpg', url: 'mock-url' });
      const createdRecord = { 
        id: 'temp-id', userId: MOCK_USER_ID, gcsPath: 'path', contentType: 'type', 
        originalFilename: 'name', size: 100, appServedUrl: '', knowledgeCardId: null, 
        createdAt: new Date(), updatedAt: new Date() 
      };
      mockImageRecordCreate.mockResolvedValue(createdRecord);
      mockImageRecordUpdate.mockRejectedValue(new Error('Prisma Update Error'));
      const input = createMockInput();
      const result = await handleImageUploadLogic(input);
      expect(result.success).toBe(false);
      expect(result.status).toBe(500);
      expect(result.error).toBe('Prisma Update Error'); 
      expect(result.details).toBeUndefined(); 
    });
  });
}); 