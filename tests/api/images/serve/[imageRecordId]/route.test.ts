/**
 * @vitest-environment node
 */
// Removed: import { makeTestServer, TestServer } from '../../../../tests/helpers/testServer';
// No, this one doesn't use makeTestServer, it calls the handler directly.
// This file will need a different approach if we want to test it via HTTP requests to a global server.
// For now, leaving it as direct handler calls but noting it for potential future refactor.

import { GET as appHandlerGET } from '@/app/api/images/serve/[imageRecordId]/route'; // USE ALIAS
import { getServerSession } from 'next-auth/next';
import { getBucket } from '@/lib/gcs'; 
import {
    mockImageRecordFindUnique, 
} from '@/tests/helpers/apiTestSetup'; // ALIAS
import { Readable } from 'stream';
import { describe, it, expect, vi, beforeEach, afterEach, Mock } from 'vitest';
import { createMocks, RequestMethod } from 'node-mocks-http';
import { NextRequest } from 'next/server';

// --- GCS Mocks (Vitest) ---
// This specific GCS mock structure is kept local to this file due to its detailed control needs.
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
  (mockGetBucket as any)._mockFile = mockFile; 
  (mockFile as any)._mockExists = mockFileExists; 
  (mockFile as any)._mockCreateReadStream = mockCreateReadStream; 

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

vi.mock('@/lib/auth', () => ({
  authOptions: {},
}));

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

interface ImageRecordRouteContext {
  params: { imageRecordId: string }; 
}

function mockRequestAndContext(
  method: RequestMethod,
  routeParams: { imageRecordId: string },
) {
  const url = `/api/images/serve/${routeParams.imageRecordId}`;
  const { req } = createMocks({ method, url });

  const nextReq = req as unknown as NextRequest;
  (nextReq as any).nextUrl = {
    searchParams: new URLSearchParams(),
    pathname: url,
  };

  const context: ImageRecordRouteContext = { params: routeParams };
  return { req: nextReq, context };
}

describe('/api/images/serve/[imageRecordId] GET', () => {
  // This test file calls the handler directly, it does not use a test server.
  // So, the global server strategy does not directly apply here in the same way.
  // If we wanted to change it to use supertest, that would be a larger refactor for this specific file.
  // For now, its existing structure of direct handler invocation will remain.

  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    vi.resetAllMocks();
    mockGetServerSessionTyped.mockResolvedValue({ user: { id: MOCK_USER_ID } });

    mockImageRecordFindUnique.mockReset();

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
    if (mockFile)
      mockFile.mockReset().mockImplementation(() => ({
        exists: mockFileExists!,
        createReadStream: mockCreateReadStream!,
      }));
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
    expect(mockedGetBucket).not.toHaveBeenCalled(); 
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
    (mockImageRecordFindUnique as Mock).mockResolvedValue(null);
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
    (mockImageRecordFindUnique as Mock).mockResolvedValue(
      createMockImageRecord(),
    );
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
    (mockImageRecordFindUnique as Mock).mockResolvedValue(
      createMockImageRecord(),
    );
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
    (mockImageRecordFindUnique as Mock).mockRejectedValue(
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
    (mockImageRecordFindUnique as Mock).mockResolvedValue(
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
    (mockImageRecordFindUnique as Mock).mockResolvedValue(
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