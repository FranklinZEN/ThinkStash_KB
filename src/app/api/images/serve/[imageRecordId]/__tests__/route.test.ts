import { GET as appHandlerGET } from '../route'; // Import your route handler
import { getServerSession } from 'next-auth/next';
import { getBucket } from '@/lib/gcs'; // Will be mocked, then imported as mock
import { prismaMock } from 'tests/__helpers__/prisma-mock';
import { Readable } from 'stream';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createMocks, RequestMethod } from 'node-mocks-http';
import { NextRequest } from 'next/server';

// --- GCS Mocks (Vitest) ---
vi.mock('@/lib/gcs', () => {
  const mockFileExists = vi.fn();
  const mockCreateReadStream = vi.fn();
  const mockFile = vi.fn(() => ({
    exists: mockFileExists,
    createReadStream: mockCreateReadStream,
  }));
  const mockGetBucket = vi.fn(() => ({
    file: mockFile,
  }));

  // Attach nested mocks to the top-level mock for easier access in tests
  // These are custom properties we add to the mock function object itself.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (mockGetBucket as any)._mockFile = mockFile; // Expose mockFile via mockGetBucket
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (mockFile as any)._mockExists = mockFileExists; // Expose mockFileExists via mockFile
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (mockFile as any)._mockCreateReadStream = mockCreateReadStream; // Expose mockCreateReadStream via mockFile

  return {
    __esModule: true,
    getBucket: mockGetBucket,
    createGcsClient: vi.fn(),
    uploadFile: vi.fn(),
    deleteFile: vi.fn(),
    getSignedUrl: vi.fn(),
    getStorageObjectPath: vi.fn(),
  };
});

// Import the mocked version of getBucket and cast it to access our custom properties
const mockedGetBucket = getBucket as ReturnType<typeof vi.fn> & {
  _mockFile?: ReturnType<typeof vi.fn> & {
    _mockExists?: ReturnType<typeof vi.fn>;
    _mockCreateReadStream?: ReturnType<typeof vi.fn>;
  };
};

// --- NextAuth Mocks (Vitest) ---
vi.mock('next-auth/next', async (importOriginal) => {
  const actual = await importOriginal<typeof import('next-auth/next')>();
  return {
    ...actual,
    getServerSession: vi.fn(),
  };
});
const mockGetServerSessionTyped = getServerSession as ReturnType<typeof vi.fn>;

// Mock @/lib/auth (if still needed, e.g. if route handler imports authOptions directly for some reason)
// If not, this mock can be removed.
vi.mock('@/lib/auth', () => ({
  authOptions: {},
}));

// --- Typed Mocks & Variables ---
const MOCK_IMAGE_RECORD_ID = 'test-image-record-id';
const MOCK_USER_ID = 'user-123';
const MOCK_GCS_PATH = 'user-123/test-image.jpg';
const MOCK_CONTENT_TYPE = 'image/jpeg';

const createMockImageRecord = (overrides = {}) => ({
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
  ...overrides,
});

// Helper to create a mock NextRequest and context for dynamic routes
interface ImageRecordRouteContext {
  params: { imageRecordId: string }; // Params are the resolved object directly
}

function mockRequestAndContext(
  method: RequestMethod,
  routeParams: { imageRecordId: string },
) {
  const url = `/api/images/serve/${routeParams.imageRecordId}`;
  const { req } = createMocks({ method, url });

  const nextReq = req as unknown as NextRequest;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (nextReq as any).nextUrl = {
    searchParams: new URLSearchParams(),
    pathname: url,
  };

  // Context params should be the direct routeParams object
  const context: ImageRecordRouteContext = { params: routeParams };
  return { req: nextReq, context };
}

describe('/api/images/serve/[imageRecordId] GET', () => {
  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    vi.resetAllMocks();
    mockGetServerSessionTyped.mockResolvedValue({ user: { id: MOCK_USER_ID } });

    // Reset and configure GCS mocks using the exposed nested mock functions from mockedGetBucket
    const mockFile = mockedGetBucket._mockFile;
    const mockFileExists = mockFile?._mockExists;
    const mockCreateReadStream = mockFile?._mockCreateReadStream;

    if (mockFileExists) mockFileExists.mockReset().mockResolvedValue([true]);
    if (mockCreateReadStream)
      mockCreateReadStream.mockReset().mockImplementation(() => {
        const readable = new Readable();
        readable._read = () => {};
        process.nextTick(() => readable.push(null));
        return readable;
      });
    // Ensure mockFile itself is reset and re-implemented if it was called/configured by a previous test
    if (mockFile)
      mockFile.mockReset().mockImplementation(() => ({
        exists: mockFileExists!,
        createReadStream: mockCreateReadStream!,
      }));
    // Ensure mockedGetBucket is reset and re-implemented to return the (potentially re-configured) mockFile
    mockedGetBucket.mockReset().mockImplementation(() => ({
      file: mockFile!,
    }));

    originalEnv = { ...process.env };
    process.env.GCS_BUCKET_NAME = 'test-bucket';
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it('should return 401 if user is not authenticated', async () => {
    mockGetServerSessionTyped.mockResolvedValue(null);
    const { req, context } = mockRequestAndContext('GET', {
      imageRecordId: MOCK_IMAGE_RECORD_ID,
    });
    const response = await appHandlerGET(req, context);
    expect(response.status).toBe(401);
    expect(mockedGetBucket).not.toHaveBeenCalled(); // Assert on the top-level mockedGetBucket
  });

  it('should return 500 if GCS_BUCKET_NAME is not configured', async () => {
    delete process.env.GCS_BUCKET_NAME;
    const { req, context } = mockRequestAndContext('GET', {
      imageRecordId: MOCK_IMAGE_RECORD_ID,
    });
    const response = await appHandlerGET(req, context);
    expect(response.status).toBe(500);
    const json = await response.json();
    expect(json.error).toBe('Server configuration error for GCS bucket.');
  });

  it('should return 404 if ImageRecord is not found', async () => {
    prismaMock.imageRecord.findUnique.mockResolvedValue(null);
    const { req, context } = mockRequestAndContext('GET', {
      imageRecordId: 'non-existent-id',
    });
    const response = await appHandlerGET(req, context);
    expect(response.status).toBe(404);
    const json = await response.json();
    expect(json.error).toBe('Image not found');
    expect(mockedGetBucket).not.toHaveBeenCalled();
  });

  it('should return 404 if file does not exist in GCS', async () => {
    prismaMock.imageRecord.findUnique.mockResolvedValue(
      createMockImageRecord(),
    );
    // Specific mock for this test path
    mockedGetBucket
      ._mockFile!._mockExists!.mockReset()
      .mockResolvedValue([false]);

    const { req, context } = mockRequestAndContext('GET', {
      imageRecordId: MOCK_IMAGE_RECORD_ID,
    });
    const response = await appHandlerGET(req, context);
    expect(response.status).toBe(404);
    const json = await response.json();
    expect(json.error).toBe('Image file not found in storage');
    expect(mockedGetBucket).toHaveBeenCalled();
    expect(mockedGetBucket._mockFile!).toHaveBeenCalledWith(MOCK_GCS_PATH);
    expect(mockedGetBucket._mockFile!._mockExists!).toHaveBeenCalled();
  });

  it('should stream the image successfully with correct headers', async () => {
    prismaMock.imageRecord.findUnique.mockResolvedValue(
      createMockImageRecord(),
    );
    // Default beforeEach setup should have exists as true and a basic stream
    // Override createReadStream for specific data
    mockedGetBucket
      ._mockFile!._mockCreateReadStream!.mockReset()
      .mockImplementation(() => {
        const stream = new Readable();
        stream.push('image data chunk');
        stream.push(null);
        return stream;
      });

    const { req, context } = mockRequestAndContext('GET', {
      imageRecordId: MOCK_IMAGE_RECORD_ID,
    });
    const response = await appHandlerGET(req, context);
    expect(response.status).toBe(200);
    expect(response.headers.get('Content-Type')).toBe(MOCK_CONTENT_TYPE);
    expect(response.headers.get('Cache-Control')).toBe(
      'public, max-age=604800, immutable',
    );
    const receivedData = await response.text();
    expect(receivedData).toBe('image data chunk');
    expect(
      mockedGetBucket._mockFile!._mockCreateReadStream!,
    ).toHaveBeenCalled();
  });

  it('should return 500 if Prisma findUnique throws', async () => {
    prismaMock.imageRecord.findUnique.mockRejectedValue(
      new Error('Prisma DB Error'),
    );
    const { req, context } = mockRequestAndContext('GET', {
      imageRecordId: MOCK_IMAGE_RECORD_ID,
    });
    const response = await appHandlerGET(req, context);
    expect(response.status).toBe(500);
    const json = await response.json();
    expect(json.error).toBe('Internal Server Error');
    expect(json.details).toBe('Prisma DB Error');
  });

  it('should return 500 if GCS file.exists() throws', async () => {
    prismaMock.imageRecord.findUnique.mockResolvedValue(
      createMockImageRecord(),
    );
    mockedGetBucket
      ._mockFile!._mockExists!.mockReset()
      .mockRejectedValue(new Error('GCS exists error'));
    const { req, context } = mockRequestAndContext('GET', {
      imageRecordId: MOCK_IMAGE_RECORD_ID,
    });
    const response = await appHandlerGET(req, context);
    expect(response.status).toBe(500);
    const json = await response.json();
    expect(json.error).toBe('Internal Server Error');
    expect(json.details).toBe('GCS exists error');
  });

  it('should return 500 if GCS createReadStream throws', async () => {
    prismaMock.imageRecord.findUnique.mockResolvedValue(
      createMockImageRecord(),
    );
    mockedGetBucket
      ._mockFile!._mockCreateReadStream!.mockReset()
      .mockImplementation(() => {
        throw new Error('GCS stream error');
      });
    const { req, context } = mockRequestAndContext('GET', {
      imageRecordId: MOCK_IMAGE_RECORD_ID,
    });
    const response = await appHandlerGET(req, context);
    expect(response.status).toBe(500);
    const json = await response.json();
    expect(json.error).toBe('Internal Server Error');
    expect(json.details).toBe('GCS stream error');
  });
});
