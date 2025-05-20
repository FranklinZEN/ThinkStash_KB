// Define mocks for GCS utility functions FIRST
const mockGcsFileExistsFn = jest.fn();
const mockGcsCreateReadStreamFn = jest.fn();
const mockGcsFileFn = jest.fn(() => ({
  exists: mockGcsFileExistsFn,
  createReadStream: mockGcsCreateReadStreamFn,
}));
const mockActualGetBucketFn = jest.fn(() => ({
  file: mockGcsFileFn,
}));

// Imports that are NOT mocked directly by jest.mock
import 'next-test-api-route-handler'; // Must be first
import { testApiHandler } from 'next-test-api-route-handler';
import { NextRequest, NextResponse } from 'next/server'; // Import Next types for the interface
// import * as appHandler from '../route'; // Delay import until after doMock
import { getServerSession } from 'next-auth';
import prisma from '@/lib/prisma';
import { Readable } from 'stream';

// Mock next-auth and prisma as before (these are hoisted)
jest.mock('next-auth', () => ({
  getServerSession: jest.fn(),
}));

jest.mock('@/lib/prisma', () => ({
  imageRecord: {
    findUnique: jest.fn(),
  },
}));

// Define an expected type for your route handler module
interface AppRouteHandlerModule {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  GET?: (request: NextRequest, context: any) => Promise<NextResponse>;
  // Add other HTTP methods like POST, PUT, DELETE if your handler exports them
}

let appHandler: AppRouteHandlerModule; // Use the defined type

const MOCK_IMAGE_RECORD_ID = 'test-image-record-id';
const MOCK_USER_ID = 'user-123';
const MOCK_GCS_PATH = 'user-123/test-image.jpg';
const MOCK_CONTENT_TYPE = 'image/jpeg';

const mockGetServerSessionTyped = getServerSession as jest.Mock;
const mockPrismaImageRecordFindUniqueTyped = prisma.imageRecord
  .findUnique as jest.Mock;

describe('/api/images/serve/[imageRecordId] GET', () => {
  let originalEnv: NodeJS.ProcessEnv;

  beforeAll(async () => {
    // Apply the mock for @/lib/gcs here, it's not hoisted.
    jest.doMock('@/lib/gcs', () => ({
      ...jest.requireActual('@/lib/gcs'),
      getBucket: mockActualGetBucketFn, // mockActualGetBucketFn is defined above and initialized
    }));
    // Now dynamically import the appHandler AFTER the mock is in place
    appHandler = await import('../route');
  });

  afterAll(() => {
    jest.unmock('@/lib/gcs'); // Clean up the mock
  });

  beforeEach(() => {
    mockGetServerSessionTyped.mockReset();
    mockPrismaImageRecordFindUniqueTyped.mockReset();

    mockActualGetBucketFn.mockClear();
    mockGcsFileFn.mockClear();
    mockGcsFileExistsFn.mockReset().mockResolvedValue([true]);
    mockGcsCreateReadStreamFn.mockReset().mockImplementation(() => {
      const readable = new Readable();
      readable._read = () => {};
      process.nextTick(() => readable.push(null));
      return readable;
    });
    mockActualGetBucketFn.mockImplementation(() => ({ file: mockGcsFileFn }));

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
    expect(mockActualGetBucketFn).not.toHaveBeenCalled();
  });

  it('should return 500 if GCS_BUCKET_NAME is not configured in the route', async () => {
    const originalBucketEnv = process.env.GCS_BUCKET_NAME;
    delete process.env.GCS_BUCKET_NAME;
    mockGetServerSessionTyped.mockResolvedValue({ user: { id: MOCK_USER_ID } });

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
    mockGetServerSessionTyped.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    mockPrismaImageRecordFindUniqueTyped.mockResolvedValue(null);
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
    expect(mockActualGetBucketFn).not.toHaveBeenCalled();
  });

  it('should return 404 if file does not exist in GCS', async () => {
    mockGetServerSessionTyped.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    mockPrismaImageRecordFindUniqueTyped.mockResolvedValue({
      id: MOCK_IMAGE_RECORD_ID,
      gcsPath: MOCK_GCS_PATH,
      contentType: MOCK_CONTENT_TYPE,
      userId: MOCK_USER_ID,
    });
    mockGcsFileExistsFn.mockResolvedValue([false]);

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
    expect(mockActualGetBucketFn).toHaveBeenCalled();
    expect(mockGcsFileFn).toHaveBeenCalledWith(MOCK_GCS_PATH);
    expect(mockGcsFileExistsFn).toHaveBeenCalled();
  });

  it('should stream the image successfully with correct headers if found', async () => {
    mockGetServerSessionTyped.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    mockPrismaImageRecordFindUniqueTyped.mockResolvedValue({
      id: MOCK_IMAGE_RECORD_ID,
      gcsPath: MOCK_GCS_PATH,
      contentType: MOCK_CONTENT_TYPE,
      userId: MOCK_USER_ID,
    });
    mockGcsFileExistsFn.mockResolvedValue([true]);
    mockGcsCreateReadStreamFn.mockImplementation(() => {
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
    expect(mockActualGetBucketFn).toHaveBeenCalled();
    expect(mockGcsFileFn).toHaveBeenCalledWith(MOCK_GCS_PATH);
    expect(mockGcsFileExistsFn).toHaveBeenCalled();
    expect(mockGcsCreateReadStreamFn).toHaveBeenCalled();
  });

  it('should return 500 if Prisma findUnique throws an error', async () => {
    mockGetServerSessionTyped.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    mockPrismaImageRecordFindUniqueTyped.mockRejectedValue(
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
    expect(mockActualGetBucketFn).not.toHaveBeenCalled();
  });

  it('should return 500 if GCS file.exists() throws an error', async () => {
    mockGetServerSessionTyped.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    mockPrismaImageRecordFindUniqueTyped.mockResolvedValue({
      id: MOCK_IMAGE_RECORD_ID,
      gcsPath: MOCK_GCS_PATH,
      contentType: MOCK_CONTENT_TYPE,
      userId: MOCK_USER_ID,
    });
    mockGcsFileExistsFn.mockRejectedValue(new Error('GCS exists error'));

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
    mockGetServerSessionTyped.mockResolvedValue({ user: { id: MOCK_USER_ID } });
    mockPrismaImageRecordFindUniqueTyped.mockResolvedValue({
      id: MOCK_IMAGE_RECORD_ID,
      gcsPath: MOCK_GCS_PATH,
      contentType: MOCK_CONTENT_TYPE,
      userId: MOCK_USER_ID,
    });
    mockGcsFileExistsFn.mockResolvedValue([true]);
    mockGcsCreateReadStreamFn.mockImplementation(() => {
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
