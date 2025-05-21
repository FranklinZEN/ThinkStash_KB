/**
 * @jest-environment node
 */
import 'next-test-api-route-handler'; // Must be first
import { testApiHandler } from 'next-test-api-route-handler';
import * as appHandler from '../route'; // Import your route handler
import { getServerSession } from 'next-auth';
import prisma from '@/lib/prisma';
import { uploadFile } from '@/lib/gcs';

// Mock next-auth
jest.mock('next-auth', () => ({
  getServerSession: jest.fn(),
}));

// Mock Prisma
jest.mock('@/lib/prisma', () => ({
  imageRecord: {
    create: jest.fn(),
    update: jest.fn(),
  },
}));

// Mock GCS uploadFile
jest.mock('@/lib/gcs', () => ({
  ...jest.requireActual('@/lib/gcs'), // Import and retain other actual exports
  uploadFile: jest.fn(),
}));

const mockGetServerSession = getServerSession as jest.Mock;
const mockPrismaImageRecordCreate = prisma.imageRecord.create as jest.Mock;
const mockPrismaImageRecordUpdate = prisma.imageRecord.update as jest.Mock;
const mockUploadFile = uploadFile as jest.Mock;

const MOCK_USER_ID = 'user-123';
const MOCK_EXTERNAL_IMAGE_URL = 'http://example.com/test-image.jpg';
const MOCK_VALID_IMAGE_RECORD_ID = 'new-image-record-id';

describe('/api/images/import-by-url POST', () => {
  beforeEach(() => {
    mockGetServerSession.mockReset();
    mockPrismaImageRecordCreate.mockReset();
    mockPrismaImageRecordUpdate.mockReset();
    mockUploadFile.mockReset();
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetServerSession.mockResolvedValue(null);
    await testApiHandler({
      appHandler,
      test: async ({ fetch }) => {
        const res = await fetch({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }),
        });
        expect(res.status).toBe(401);
        const json = await res.json();
        expect(json.error).toBe('Unauthorized');
      },
    });
  });

  it('should return 400 if request body is invalid JSON', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    await testApiHandler({
      appHandler,
      test: async ({ fetch }) => {
        const res = await fetch({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: 'not a valid json',
        });
        expect(res.status).toBe(400);
        const json = await res.json();
        expect(json.error).toBe('Invalid JSON format');
      },
    });
  });

  it('should return 400 if externalImageUrl is missing or invalid', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    await testApiHandler({
      appHandler,
      test: async ({ fetch }) => {
        const res = await fetch({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ externalImageUrl: 'not-a-url' }),
        });
        expect(res.status).toBe(400);
        const json = await res.json();
        expect(json.error).toBe('Invalid request body');
        expect(json.details.fieldErrors.externalImageUrl).toContain(
          'Invalid URL format',
        );
      },
    });
  });

  it('should return 400 if fetching the external image fails', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    global.fetch = jest.fn().mockResolvedValueOnce({
      ok: false,
      status: 404,
      headers: new Headers(),
    });

    await testApiHandler({
      appHandler,
      test: async ({ fetch: appFetch }) => {
        const res = await appFetch({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }),
        });
        expect(res.status).toBe(400);
        const json = await res.json();
        expect(json.error).toBe('Failed to download image from URL');
      },
    });
  });

  // TODO: Add tests for content type validation
  it('should return 400 if external image content type is not supported', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    global.fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      headers: new Headers({
        'content-type': 'image/bmp', // Unsupported type
        'content-length': '100',
      }),
      arrayBuffer: async () => Buffer.from('data').buffer,
    });

    await testApiHandler({
      appHandler,
      test: async ({ fetch: appFetch }) => {
        const res = await appFetch({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }),
        });
        expect(res.status).toBe(400);
        const json = await res.json();
        expect(json.error).toBe(
          'Invalid image type. Allowed types: image/jpeg, image/png, image/gif, image/webp',
        );
      },
    });
  });

  // TODO: Add tests for file size validation (from headers and from buffer)
  it('should return 400 if external image content-length header exceeds max size', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    global.fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      headers: new Headers({
        'content-type': 'image/jpeg',
        'content-length': (6 * 1024 * 1024).toString(), // 6MB, assuming MAX_SIZE_IN_MB = 5
      }),
      arrayBuffer: async () => Buffer.from('data').buffer, // Buffer content doesn't matter here
    });

    await testApiHandler({
      appHandler,
      test: async ({ fetch: appFetch }) => {
        const res = await appFetch({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }),
        });
        expect(res.status).toBe(400);
        const json = await res.json();
        expect(json.error).toBe('Image is too large. Maximum size: 5MB');
      },
    });
  });

  it('should return 400 if external image buffer exceeds max size', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    const largeBuffer = Buffer.alloc(6 * 1024 * 1024); // 6MB
    global.fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      headers: new Headers({
        'content-type': 'image/jpeg',
        // No content-length or a misleading one, actual buffer check should catch it
      }),
      arrayBuffer: async () => largeBuffer.buffer,
    });

    await testApiHandler({
      appHandler,
      test: async ({ fetch: appFetch }) => {
        const res = await appFetch({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }),
        });
        expect(res.status).toBe(400);
        const json = await res.json();
        expect(json.error).toBe('Image is too large. Maximum size: 5MB');
      },
    });
  });

  it('should successfully import image, create record, and return appServedUrl', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: MOCK_USER_ID } });

    // Mock successful fetch of external image
    const mockImageBuffer = Buffer.from('mock image data');
    global.fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      headers: new Headers({
        'content-type': 'image/jpeg',
        'content-length': mockImageBuffer.length.toString(),
      }),
      arrayBuffer: async () => mockImageBuffer.buffer,
    });

    // Mock successful GCS upload
    const mockGcsFile = {
      filename: 'gcs-generated-filename.jpg',
      contentType: 'image/jpeg',
      size: mockImageBuffer.length,
      url: 'http://fake-gcs-url.com/gcs-generated-filename.jpg', // uploadFile might return a signed URL or other URL
    };
    mockUploadFile.mockResolvedValue(mockGcsFile);

    // Mock Prisma create and update
    const initialImageRecord = {
      id: MOCK_VALID_IMAGE_RECORD_ID,
      userId: MOCK_USER_ID,
      gcsPath: mockGcsFile.filename,
      contentType: mockGcsFile.contentType,
      originalFilename: 'test-image.jpg', // This would be derived by the handler
      size: mockGcsFile.size,
      appServedUrl: '', // Placeholder before update
      knowledgeCardId: null,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    mockPrismaImageRecordCreate.mockResolvedValue(initialImageRecord);

    const finalAppServedUrl = `/api/images/serve/${MOCK_VALID_IMAGE_RECORD_ID}`;
    const updatedImageRecord = {
      ...initialImageRecord,
      appServedUrl: finalAppServedUrl,
    };
    mockPrismaImageRecordUpdate.mockResolvedValue(updatedImageRecord);

    await testApiHandler({
      appHandler,
      test: async ({ fetch: appFetch }) => {
        const res = await appFetch({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }),
        });
        expect(res.status).toBe(200);
        const json = await res.json();
        expect(json.success).toBe(true);
        expect(json.appServedUrl).toBe(finalAppServedUrl);
        expect(json.imageRecordId).toBe(MOCK_VALID_IMAGE_RECORD_ID);

        expect(mockUploadFile).toHaveBeenCalled();
        expect(mockPrismaImageRecordCreate).toHaveBeenCalledWith({
          data: expect.objectContaining({
            userId: MOCK_USER_ID,
            gcsPath: mockGcsFile.filename,
            contentType: mockGcsFile.contentType,
            size: mockGcsFile.size,
            appServedUrl: '',
          }),
        });
        expect(mockPrismaImageRecordUpdate).toHaveBeenCalledWith({
          where: { id: MOCK_VALID_IMAGE_RECORD_ID },
          data: { appServedUrl: finalAppServedUrl },
        });
      },
    });
  });

  it('should return 500 if uploadFile to GCS fails', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    global.fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      headers: new Headers({
        'content-type': 'image/jpeg',
        'content-length': '100',
      }),
      arrayBuffer: async () => Buffer.from('data').buffer,
    });
    mockUploadFile.mockRejectedValue(new Error('GCS Upload Error'));

    await testApiHandler({
      appHandler,
      test: async ({ fetch: appFetch }) => {
        const res = await appFetch({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }),
        });
        expect(res.status).toBe(500);
        const json = await res.json();
        expect(json.error).toBe('Failed to import image by URL');
        expect(json.details).toBe('GCS Upload Error');
      },
    });
  });

  it('should return 500 if Prisma create fails', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    global.fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      headers: new Headers({
        'content-type': 'image/jpeg',
        'content-length': '100',
      }),
      arrayBuffer: async () => Buffer.from('data').buffer,
    });
    mockUploadFile.mockResolvedValue({
      filename: 'gcs.jpg',
      contentType: 'image/jpeg',
      size: 100,
      url: 'gcs-url',
    });
    mockPrismaImageRecordCreate.mockRejectedValue(
      new Error('Prisma Create Error'),
    );

    await testApiHandler({
      appHandler,
      test: async ({ fetch: appFetch }) => {
        const res = await appFetch({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }),
        });
        expect(res.status).toBe(500);
        const json = await res.json();
        expect(json.error).toBe('Failed to import image by URL');
        expect(json.details).toBe('Prisma Create Error');
      },
    });
  });

  // TODO: Add test for Prisma update failure
  it('should return 500 if Prisma update for appServedUrl fails', async () => {
    mockGetServerSession.mockResolvedValue({ user: { id: MOCK_USER_ID } });

    const mockImageBuffer = Buffer.from('mock image data');
    global.fetch = jest.fn().mockResolvedValueOnce({
      ok: true,
      headers: new Headers({
        'content-type': 'image/jpeg',
        'content-length': mockImageBuffer.length.toString(),
      }),
      arrayBuffer: async () => mockImageBuffer.buffer,
    });

    const mockGcsFile = {
      filename: 'gcs-generated-filename.jpg',
      contentType: 'image/jpeg',
      size: mockImageBuffer.length,
      url: 'http://fake-gcs-url.com/gcs-generated-filename.jpg',
    };
    mockUploadFile.mockResolvedValue(mockGcsFile);

    const initialImageRecord = {
      id: MOCK_VALID_IMAGE_RECORD_ID,
      userId: MOCK_USER_ID,
      gcsPath: mockGcsFile.filename,
      contentType: mockGcsFile.contentType,
      originalFilename: 'test-image.jpg',
      size: mockGcsFile.size,
      appServedUrl: '',
      knowledgeCardId: null,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    mockPrismaImageRecordCreate.mockResolvedValue(initialImageRecord);

    // Mock Prisma update failure
    mockPrismaImageRecordUpdate.mockRejectedValue(
      new Error('Prisma Update Error'),
    );

    await testApiHandler({
      appHandler,
      test: async ({ fetch: appFetch }) => {
        const res = await appFetch({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }),
        });
        expect(res.status).toBe(500);
        const json = await res.json();
        expect(json.error).toBe('Failed to import image by URL');
        expect(json.details).toBe('Prisma Update Error');

        // Verify that create was still called
        expect(mockPrismaImageRecordCreate).toHaveBeenCalledWith({
          data: expect.objectContaining({
            userId: MOCK_USER_ID,
            gcsPath: mockGcsFile.filename,
          }),
        });
        // Verify that update was attempted
        expect(mockPrismaImageRecordUpdate).toHaveBeenCalledWith({
          where: { id: MOCK_VALID_IMAGE_RECORD_ID },
          data: {
            appServedUrl: `/api/images/serve/${MOCK_VALID_IMAGE_RECORD_ID}`,
          },
        });
      },
    });
  });
});
