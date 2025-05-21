// Define GCS mock functions that will be used by the jest.mock implementation
// Using var here to help with Jest hoisting and initialization order issues.

// These will be assigned jest.fn() after the jest.mock call for @/lib/gcs
// eslint-disable-next-line no-var
var gcsFileExists_mock: jest.Mock;
// eslint-disable-next-line no-var
var gcsCreateReadStream_mock: jest.Mock;
// eslint-disable-next-line no-var
var gcsFile_mock: jest.Mock; // This will mock the function returned by bucket.file()
// eslint-disable-next-line no-var
var getBucket_actualMock: jest.Mock; // This will mock the getBucket export

import 'next-test-api-route-handler'; // Must be first
import { testApiHandler } from 'next-test-api-route-handler';
import * as appHandler from '../route'; // Use static import now
import { prismaMock } from 'tests/__helpers__/prisma-mock'; // Import the actual mock
import { Readable } from 'stream';

// --- MOCKS ---
// Mock @/lib/auth to control authOptions
jest.mock('@/lib/auth', () => ({
  authOptions: {},
}));

// Mock next-auth (Revised Strategy)
// eslint-disable-next-line no-var
var mockGetServerSessionFn: jest.Mock; // Hoisted and initialized to undefined

jest.mock('next-auth/next', () => {
  const actualNextAuthNext = jest.requireActual('next-auth/next');
  return {
    __esModule: true,
    ...actualNextAuthNext,
    getServerSession: (...args: unknown[]) => mockGetServerSessionFn(...args), // Use unknown[] for args
  };
});

// Initialize after jest.mock has been processed by Jest
mockGetServerSessionFn = jest.fn();
const mockGetServerSessionTyped = mockGetServerSessionFn;

// Mock @/lib/gcs using a standard top-level jest.mock
jest.mock('@/lib/gcs', () => ({
  __esModule: true,
  // The factory calls the getBucket_actualMock which will be defined later
  getBucket: (...args: unknown[]) => getBucket_actualMock(...args), // Use unknown[] for args
}));

// Initialize the GCS mock functions AFTER jest.mock has been declared
gcsFileExists_mock = jest.fn();
gcsCreateReadStream_mock = jest.fn();
gcsFile_mock = jest.fn(() => ({
  exists: gcsFileExists_mock,
  createReadStream: gcsCreateReadStream_mock,
}));
getBucket_actualMock = jest.fn(() => ({
  file: gcsFile_mock,
}));

// --- Typed Mocks & Variables ---
const MOCK_IMAGE_RECORD_ID = 'test-image-record-id';
const MOCK_USER_ID = 'user-123';
const MOCK_GCS_PATH = 'user-123/test-image.jpg';
const MOCK_CONTENT_TYPE = 'image/jpeg';

// Helper for a complete ImageRecord mock
const createMockImageRecord = (
  overrides: Partial<
    NonNullable<Awaited<ReturnType<typeof prismaMock.imageRecord.findUnique>>>
  > = {},
) => {
  const defaultRecord = {
    id: MOCK_IMAGE_RECORD_ID,
    userId: MOCK_USER_ID,
    gcsPath: MOCK_GCS_PATH,
    contentType: MOCK_CONTENT_TYPE,
    originalFilename: 'test-image.jpg',
    size: 12345,
    appServedUrl: `/api/images/serve/${MOCK_IMAGE_RECORD_ID}`,
    knowledgeCardId: null,
    createdAt: new Date(),
    updatedAt: new Date(),
  };
  return { ...defaultRecord, ...overrides };
};

describe('/api/images/serve/[imageRecordId] GET', () => {
  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    // prismaMock is reset in tests/__helpers__/prisma-mock.ts
    mockGetServerSessionTyped.mockReset();
    mockGetServerSessionTyped.mockResolvedValue({ user: { id: MOCK_USER_ID } });

    // Reset GCS mocks
    getBucket_actualMock.mockClear(); // Clear calls to the main getBucket mock
    gcsFile_mock.mockClear(); // Clear calls to the file() mock
    gcsFileExists_mock.mockReset().mockResolvedValue([true]);
    gcsCreateReadStream_mock.mockReset().mockImplementation(() => {
      const readable = new Readable();
      readable._read = () => {};
      process.nextTick(() => readable.push(null));
      return readable;
    });

    // Ensure the getBucket_actualMock returns the structure that leads to other mocks
    getBucket_actualMock.mockImplementation(() => ({
      file: gcsFile_mock.mockImplementation(() => ({
        exists: gcsFileExists_mock,
        createReadStream: gcsCreateReadStream_mock,
      })),
    }));

    originalEnv = { ...process.env };
    process.env.GCS_BUCKET_NAME = 'test-bucket';
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetServerSessionTyped.mockResolvedValue(null);
    await testApiHandler({
      appHandler,
      params: { imageRecordId: MOCK_IMAGE_RECORD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        expect(res.status).toBe(401);
        const json = await res.json();
        expect(json.error).toBe('Unauthorized');
      },
    });
    expect(getBucket_actualMock).not.toHaveBeenCalled();
  });

  it('should return 500 if GCS_BUCKET_NAME is not configured in the route', async () => {
    const originalBucketEnv = process.env.GCS_BUCKET_NAME;
    delete process.env.GCS_BUCKET_NAME;
    await testApiHandler({
      appHandler,
      params: { imageRecordId: MOCK_IMAGE_RECORD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        expect(res.status).toBe(500);
        const json = await res.json();
        expect(json.error).toBe('Server configuration error for GCS bucket.');
      },
    });
    process.env.GCS_BUCKET_NAME = originalBucketEnv;
  });

  it('should return 404 if ImageRecord is not found in Prisma', async () => {
    prismaMock.imageRecord.findUnique.mockResolvedValue(null);
    await testApiHandler({
      appHandler,
      params: { imageRecordId: 'non-existent-id' },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        expect(res.status).toBe(404);
        const json = await res.json();
        expect(json.error).toBe('Image not found');
      },
    });
    expect(getBucket_actualMock).not.toHaveBeenCalled();
  });

  it('should return 404 if file does not exist in GCS', async () => {
    prismaMock.imageRecord.findUnique.mockResolvedValue(
      createMockImageRecord(),
    );
    gcsFileExists_mock.mockResolvedValue([false]);

    await testApiHandler({
      appHandler,
      params: { imageRecordId: MOCK_IMAGE_RECORD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        expect(res.status).toBe(404);
        const json = await res.json();
        expect(json.error).toBe('Image file not found in storage');
      },
    });
    expect(getBucket_actualMock).toHaveBeenCalled();
    expect(gcsFile_mock).toHaveBeenCalledWith(MOCK_GCS_PATH);
    expect(gcsFileExists_mock).toHaveBeenCalled();
  });

  it('should stream the image successfully with correct headers if found', async () => {
    prismaMock.imageRecord.findUnique.mockResolvedValue(
      createMockImageRecord(),
    );
    gcsFileExists_mock.mockResolvedValue([true]);
    gcsCreateReadStream_mock.mockImplementation(() => {
      const stream = new Readable();
      stream.push('image data chunk');
      stream.push(null);
      return stream;
    });

    await testApiHandler({
      appHandler,
      params: { imageRecordId: MOCK_IMAGE_RECORD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        expect(res.status).toBe(200);
        expect(res.headers.get('Content-Type')).toBe(MOCK_CONTENT_TYPE);
        expect(res.headers.get('Cache-Control')).toBe(
          'public, max-age=604800, immutable',
        );
        const receivedData = await res.text();
        expect(receivedData).toBe('image data chunk');
      },
    });
    expect(getBucket_actualMock).toHaveBeenCalled();
    expect(gcsFile_mock).toHaveBeenCalledWith(MOCK_GCS_PATH);
    expect(gcsFileExists_mock).toHaveBeenCalled();
    expect(gcsCreateReadStream_mock).toHaveBeenCalled();
  });

  it('should return 500 if Prisma findUnique throws an error', async () => {
    prismaMock.imageRecord.findUnique.mockRejectedValue(
      new Error('Prisma DB Error'),
    );
    await testApiHandler({
      appHandler,
      params: { imageRecordId: MOCK_IMAGE_RECORD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        expect(res.status).toBe(500);
        const json = await res.json();
        expect(json.error).toBe('Internal Server Error');
        expect(json.details).toBe('Prisma DB Error');
      },
    });
    expect(getBucket_actualMock).not.toHaveBeenCalled();
  });

  it('should return 500 if GCS file.exists() throws an error', async () => {
    prismaMock.imageRecord.findUnique.mockResolvedValue(
      createMockImageRecord(),
    );
    gcsFileExists_mock.mockRejectedValue(new Error('GCS exists error'));

    await testApiHandler({
      appHandler,
      params: { imageRecordId: MOCK_IMAGE_RECORD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        expect(res.status).toBe(500);
        const json = await res.json();
        expect(json.error).toBe('Internal Server Error');
        expect(json.details).toBe('GCS exists error');
      },
    });
  });

  it('should return 500 if GCS createReadStream throws an error', async () => {
    prismaMock.imageRecord.findUnique.mockResolvedValue(
      createMockImageRecord(),
    );
    gcsFileExists_mock.mockResolvedValue([true]);
    gcsCreateReadStream_mock.mockImplementation(() => {
      throw new Error('GCS stream error');
    });

    await testApiHandler({
      appHandler,
      params: { imageRecordId: MOCK_IMAGE_RECORD_ID },
      test: async ({ fetch }) => {
        const res = await fetch({ method: 'GET' });
        expect(res.status).toBe(500);
        const json = await res.json();
        expect(json.error).toBe('Internal Server Error');
        expect(json.details).toBe('GCS stream error');
      },
    });
  });
});
