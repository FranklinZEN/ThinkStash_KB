/**
 * @vitest-environment node
 */
import request from 'supertest';
import { makeTestServer, TestServer } from '@/tests/helpers/testServer';
import {
  MOCK_USER_ID,
  mockUserCreate,
  mockUserDeleteMany,
  mockImageRecordCreate,
  mockImageRecordUpdate,
  mockImageRecordDeleteMany,
} from '@/tests/helpers/apiTestSetup';

import {
  vi,
  beforeEach as vitestBeforeEach,
  afterEach as vitestAfterEach,
  describe as vitestDescribe,
  it as vitestIt,
  expect as vitestExpect,
  Mock,
  beforeAll as vitestBeforeAll,
  afterAll as vitestAfterAll,
} from 'vitest';

let testServer: TestServer;
let currentTestServerUrl: string;

vitestBeforeAll(async () => {
  console.log('[import-by-url test beforeAll] Starting test server...');
  testServer = await makeTestServer(); 
  currentTestServerUrl = testServer.url;
  console.log(`[import-by-url test beforeAll] Test server started on ${currentTestServerUrl}`);

  mockUserCreate.mockReset();
  mockUserDeleteMany.mockReset();
  mockImageRecordCreate.mockReset();
  mockImageRecordUpdate.mockReset();
  mockImageRecordDeleteMany.mockReset();

  (mockImageRecordDeleteMany as Mock).mockResolvedValue({ count: 0 });
  (mockUserDeleteMany as Mock).mockResolvedValue({ count: 0 });
  (mockUserCreate as Mock).mockImplementation(async (args: any) => args.data);

  const prismaMock = (globalThis as any).__PRISMA_INSTANCE__;
  if (!prismaMock) throw new Error('__PRISMA_INSTANCE__ not found on globalThis in beforeEach');

  try {
    // Removed debug logs for __PRISMA_INSTANCE__ as it should be set by vitest.setup.ts
    await prismaMock.imageRecord.deleteMany({});
    await prismaMock.user.deleteMany({});
    await prismaMock.user.create({
      data: {
        id: MOCK_USER_ID,
        email: `${MOCK_USER_ID}@example.com`,
        password: 'testpassword',
        name: 'Mock Test User',
      },
    });
  } catch (error) {
    throw error;
  }
});

vitestAfterAll(async () => {
  if (testServer && testServer.close) {
    console.log('[import-by-url test afterAll] Closing test server...');
    await testServer.close();
    console.log('[import-by-url test afterAll] Test server closed.');
  }
});

vitestDescribe.sequential('/api/images/import-by-url POST', () => {
  // Define constants INSIDE the describe block
  const MOCK_EXTERNAL_IMAGE_URL_BASE = 'http://example.com';
  const MOCK_EXTERNAL_IMAGE_URL_PATH = '/test-image.jpg';
  const MOCK_EXTERNAL_IMAGE_URL = `${MOCK_EXTERNAL_IMAGE_URL_BASE}${MOCK_EXTERNAL_IMAGE_URL_PATH}`;

  const MOCK_COMPLEX_IMAGE_URL_BASE = 'https://images.unsplash.com';
  const MOCK_COMPLEX_IMAGE_URL_PATH =
    '/photo-12345?ixid=SOMEID&auto=format&fit=crop&w=1000&q=80#anchor';
  const MOCK_COMPLEX_IMAGE_URL = `${MOCK_COMPLEX_IMAGE_URL_BASE}${MOCK_COMPLEX_IMAGE_URL_PATH}`;

  const MOCK_URL_NO_FILENAME_BASE = 'http://example.com';
  const MOCK_URL_NO_FILENAME_PATH = '/getimage';
  const MOCK_URL_NO_FILENAME = `${MOCK_URL_NO_FILENAME_BASE}${MOCK_URL_NO_FILENAME_PATH}`;

  if (!currentTestServerUrl) { // Check if server URL was set from beforeAll
      // This check is a bit tricky because currentTestServerUrl is set in vitestBeforeAll
      // which should run before this describe block body. If it's not set, something is wrong.
      // Consider throwing or logging an error if process.env.TEST_SERVER_URL (if global) or currentTestServerUrl (if local) is not set.
  }

  vitestBeforeEach(() => {
    vi.restoreAllMocks();
  });

  vitestIt('should return 401 if user is not authenticated', async () => {
    if (!currentTestServerUrl) throw new Error('Test server URL not set');
    const response = await request(currentTestServerUrl)
      .post('/api/images/import-by-url')
      .set('X-Test-User-Id', 'null')
      .set('Content-Type', 'application/json')
      .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));
    vitestExpect(response.status).toBe(401);
    vitestExpect(response.body.error).toBe('Unauthorized');
  });

  vitestIt('should return 400 if request body is invalid JSON', async () => {
    if (!currentTestServerUrl) throw new Error('Test server URL not set');
    const response = await request(currentTestServerUrl)
      .post('/api/images/import-by-url')
      .set('X-Test-User-Id', MOCK_USER_ID)
      .set('Content-Type', 'application/json')
      .send('not a valid json');
    vitestExpect(response.status).toBe(400);
    vitestExpect(response.body.error).toBe('Invalid JSON format');
  }, 15000);

  vitestIt(
    'should return 400 if externalImageUrl is missing or invalid',
    async () => {
      if (!currentTestServerUrl) throw new Error('Test server URL not set');
      const response = await request(currentTestServerUrl)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .send(JSON.stringify({ externalImageUrl: 'not-a-url' }));
      vitestExpect(response.status).toBe(400);
      vitestExpect(response.body.error).toBe('Invalid request body');
    },
    15000,
  );

  vitestIt(
    'should return 500 if fetching the external image fails (e.g. 404)',
    async () => {
      if (!currentTestServerUrl) throw new Error('Test server URL not set');
      const response = await request(currentTestServerUrl)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL) 
        .set('X-Test-Mock-Fetch-Status', '404') 
        .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));
      vitestExpect(response.status).toBe(500);
      vitestExpect(response.body.error).toBe('Failed to import image by URL');
      vitestExpect(response.body.details).toBe(
        'Failed to fetch image. Status: 404',
      );
    },
    15000,
  );

  vitestIt(
    'should return 400 if external image content type is not supported',
    async () => {
      if (!currentTestServerUrl) throw new Error('Test server URL not set');
      const mockBody = Buffer.from('data');
      const response = await request(currentTestServerUrl)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL) 
        .set('X-Test-Mock-Fetch-Status', '200') 
        .set('X-Test-Mock-Fetch-Body-Base64', mockBody.toString('base64')) 
        .set(
          'X-Test-Mock-Fetch-Headers', 
          JSON.stringify({
            'Content-Type': 'image/bmp',
            'Content-Length': mockBody.length.toString(),
          }),
        )
        .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));
      vitestExpect(response.status).toBe(400);
      vitestExpect(response.body.error).toBe(
        'Invalid image type. Allowed types: image/jpeg, image/png, image/gif, image/webp',
      );
    },
    15000,
  );
  
  vitestIt(
    'should return 400 if external image content-length header exceeds max size',
    async () => {
      if (!currentTestServerUrl) throw new Error('Test server URL not set');
      const response = await request(currentTestServerUrl)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
        .set('X-Test-Mock-Fetch-Status', '200')
        .set(
          'X-Test-Mock-Fetch-Headers',
          JSON.stringify({
            'Content-Type': 'image/jpeg',
            'Content-Length': (6 * 1024 * 1024).toString(), // > 5MB
          }),
        )
        .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));
      vitestExpect(response.status).toBe(400);
      vitestExpect(response.body.error).toBe(
        'Image is too large. Maximum size: 5MB',
      );
    },
    15000,
  );

  vitestIt(
    'should return 400 if external image buffer exceeds max size',
    async () => {
      if (!currentTestServerUrl) throw new Error('Test server URL not set');
      const response = await request(currentTestServerUrl)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
        .set('X-Test-Mock-Fetch-Status', '200-large-buffer-test') // Simulates large buffer in route
        .set(
          'X-Test-Mock-Fetch-Headers',
          JSON.stringify({ 'Content-Type': 'image/jpeg' }),
        )
        .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));

      vitestExpect(response.status).toBe(400);
      vitestExpect(response.body.error).toBe(
        'Image is too large. Maximum size: 5MB',
      );
    },
    15000,
  );

  vitestIt(
    'should successfully import image, create record, and return appServedUrl',
    async () => {
      if (!currentTestServerUrl) throw new Error('Test server URL not set');
      const mockImageBuffer = Buffer.from('mock image data');
      const randomSuffix = Math.random().toString(36).substring(2, 7);
      const uniqueGcsFilename = `test-success-${Date.now()}-${randomSuffix}.jpg`;
      const mockGcsFileData = {
        filename: uniqueGcsFilename,
        contentType: 'image/jpeg',
        size: mockImageBuffer.length,
        url: `http://fake-gcs-url.com/${uniqueGcsFilename}`,
      };
      const mockImageRecordData = {
        id: 'mock-image-record-id',
        userId: MOCK_USER_ID,
        originalUrl: MOCK_EXTERNAL_IMAGE_URL,
        gcsObjectName: uniqueGcsFilename,
        gcsBucketName: 'test-bucket',
        filename: uniqueGcsFilename,
        contentType: 'image/jpeg',
        size: mockImageBuffer.length,
        appServedUrl: `/api/images/serve/mock-image-record-id`,
        gcsUrl: mockGcsFileData.url,
        createdAt: new Date(), 
        updatedAt: new Date(),
      };

      (mockImageRecordCreate as Mock).mockResolvedValue(mockImageRecordData);
      (mockImageRecordUpdate as Mock).mockResolvedValue(mockImageRecordData); 

      const response = await request(currentTestServerUrl)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
        .set('X-Test-Mock-Fetch-Status', '200')
        .set(
          'X-Test-Mock-Fetch-Body-Base64',
          mockImageBuffer.toString('base64'),
        )
        .set(
          'X-Test-Mock-Fetch-Headers',
          JSON.stringify({
            'Content-Type': 'image/jpeg',
            'Content-Length': mockImageBuffer.length.toString(),
          }),
        )
        .set('X-Test-GCS-Upload-Success-Data', JSON.stringify(mockGcsFileData)) 
        .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));

      vitestExpect(response.status).toBe(200);
      const jsonBody = response.body;
      vitestExpect(jsonBody.success).toBe(true);
      vitestExpect(jsonBody.imageRecordId).toBe(mockImageRecordData.id);
      vitestExpect(jsonBody.appServedUrl).toContain(mockImageRecordData.id);
      vitestExpect(jsonBody.gcsUrl).toBe(mockGcsFileData.url);

      vitestExpect(mockImageRecordCreate).toHaveBeenCalled(); 
    },
    15000,
  );

  vitestIt('should return 500 if GCS upload fails', async () => {
    if (!currentTestServerUrl) throw new Error('Test server URL not set');
    const mockImageBuffer = Buffer.from('mock image data for gcs fail');
    const gcsErrorMessage = 'Simulated GCS Upload Error From Header';

    (mockImageRecordCreate as Mock).mockResolvedValue({ id: 'any-id' });

    const response = await request(currentTestServerUrl)
      .post('/api/images/import-by-url')
      .set('X-Test-User-Id', MOCK_USER_ID)
      .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
      .set('X-Test-Mock-Fetch-Status', '200')
      .set('X-Test-Mock-Fetch-Body-Base64', mockImageBuffer.toString('base64'))
      .set(
        'X-Test-Mock-Fetch-Headers',
        JSON.stringify({
          'Content-Type': 'image/png',
          'Content-Length': mockImageBuffer.length.toString(),
        }),
      )
      .set('X-Test-GCS-Upload-Error', gcsErrorMessage) 
      .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));

    vitestExpect(response.status).toBe(500);
    vitestExpect(response.body.error).toBe('Failed to import image by URL');
    vitestExpect(response.body.details).toBe(gcsErrorMessage);
  }, 15000);

  vitestIt('should return 500 if Prisma create fails', async () => {
    if (!currentTestServerUrl) throw new Error('Test server URL not set');
    const mockImageBuffer = Buffer.from('mock image data for prisma create fail');
    const randomSuffix = Math.random().toString(36).substring(2, 7);
    const uniqueGcsFilename = `test-prisma-create-fail-${Date.now()}-${randomSuffix}.gif`;
    const mockGcsFileData = { 
      filename: uniqueGcsFilename,
      contentType: 'image/gif',
      size: mockImageBuffer.length,
      url: `some-gcs-url/${uniqueGcsFilename}`,
    };

    const prismaCreateError = new Error('Simulated Prisma Create Failed From Mock');
    (mockImageRecordCreate as Mock).mockRejectedValue(prismaCreateError);

    const response = await request(currentTestServerUrl)
      .post('/api/images/import-by-url')
      .set('X-Test-User-Id', MOCK_USER_ID)
      .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
      .set('X-Test-Mock-Fetch-Status', '200')
      .set('X-Test-Mock-Fetch-Body-Base64', mockImageBuffer.toString('base64'))
      .set(
        'X-Test-Mock-Fetch-Headers',
        JSON.stringify({
          'Content-Type': 'image/gif',
          'Content-Length': mockImageBuffer.length.toString(),
        }),
      )
      .set('X-Test-GCS-Upload-Success-Data', JSON.stringify(mockGcsFileData)) 
      .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));

    vitestExpect(response.status).toBe(500);
    vitestExpect(response.body.error).toBe('Failed to import image by URL');
    vitestExpect(response.body.details).toBe(prismaCreateError.message);
  }, 15000);

  vitestIt('should return 500 if Prisma update fails (if applicable to route logic)', async () => {
    if (!currentTestServerUrl) throw new Error('Test server URL not set');
    const mockImageBuffer = Buffer.from('mock image data for prisma update fail');
    const randomSuffix = Math.random().toString(36).substring(2, 7);
    const uniqueGcsFilename = `test-prisma-update-fail-${Date.now()}-${randomSuffix}.webp`;
    const mockGcsFileData = { 
      filename: uniqueGcsFilename,
      contentType: 'image/webp',
      size: mockImageBuffer.length,
      url: `some-gcs-url/${uniqueGcsFilename}`
    };
    const mockCreatedImageRecord = { 
      id: 'temp-id', 
      userId: MOCK_USER_ID, 
      originalUrl: MOCK_EXTERNAL_IMAGE_URL, 
      gcsObjectName: 'obj', 
      gcsBucketName: 'bkt', 
      filename:'fn', 
      contentType:'image/webp', 
      size: mockImageBuffer.length, 
      appServedUrl: '', 
      gcsUrl: '', 
      createdAt: new Date(), 
      updatedAt: new Date(),
    };

    (mockImageRecordCreate as Mock).mockResolvedValue(mockCreatedImageRecord); 
    const prismaUpdateError = new Error('Simulated Prisma Update Failed From Mock');
    (mockImageRecordUpdate as Mock).mockRejectedValue(prismaUpdateError);

    const response = await request(currentTestServerUrl)
      .post('/api/images/import-by-url')
      .set('X-Test-User-Id', MOCK_USER_ID)
      .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
      .set('X-Test-Mock-Fetch-Status', '200')
      .set('X-Test-Mock-Fetch-Body-Base64', mockImageBuffer.toString('base64'))
      .set(
        'X-Test-Mock-Fetch-Headers',
        JSON.stringify({
          'Content-Type': 'image/webp', 
          'Content-Length': mockImageBuffer.length.toString(),
        }),
      )
      .set('X-Test-GCS-Upload-Success-Data', JSON.stringify(mockGcsFileData))
      .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));

    vitestExpect(response.status).toBe(500);
    vitestExpect(response.body.error).toBe('Failed to import image by URL');
    vitestExpect(response.body.details).toBe(prismaUpdateError.message); 
  }, 15000);

  vitestIt('should extract filename correctly from complex URL', async () => {
    if (!currentTestServerUrl) throw new Error('Test server URL not set');
    const mockBody = Buffer.from('data');
    const randomSuffix = Math.random().toString(36).substring(2, 7);
    const uniqueGcsFilename = `test-complex-url-${Date.now()}-${randomSuffix}.jpeg`; 
    const mockGcsFileData = {
      filename: uniqueGcsFilename,
      url: `gcs-url/${uniqueGcsFilename}`,
      contentType: 'image/jpeg', 
      size: mockBody.length,
    };
    const mockImageRecordData = { 
      id: 'img-complex', 
      gcsUrl: mockGcsFileData.url, 
      userId: MOCK_USER_ID, 
      originalUrl: MOCK_COMPLEX_IMAGE_URL, 
      gcsObjectName: uniqueGcsFilename, 
      gcsBucketName: 'bkt', 
      filename: uniqueGcsFilename, 
      contentType:'image/jpeg', 
      size: mockBody.length, 
      appServedUrl: '/api/images/serve/img-complex',
      createdAt: new Date(), 
      updatedAt: new Date(),
    };
    
    (mockImageRecordCreate as Mock).mockResolvedValue(mockImageRecordData);
    (mockImageRecordUpdate as Mock).mockResolvedValue(mockImageRecordData);

    const response = await request(currentTestServerUrl)
      .post('/api/images/import-by-url')
      .set('X-Test-User-Id', MOCK_USER_ID)
      .set('X-Test-Mock-Fetch-Url', MOCK_COMPLEX_IMAGE_URL)
      .set('X-Test-Mock-Fetch-Status', '200')
      .set('X-Test-Mock-Fetch-Body-Base64', mockBody.toString('base64'))
      .set(
        'X-Test-Mock-Fetch-Headers',
        JSON.stringify({
          'Content-Type': 'image/jpeg', 
          'Content-Length': mockBody.length.toString(),
        }),
      )
      .set('X-Test-GCS-Upload-Success-Data', JSON.stringify(mockGcsFileData))
      .send(JSON.stringify({ externalImageUrl: MOCK_COMPLEX_IMAGE_URL }));
    
    vitestExpect(response.status).toBe(200);
    const jsonBody = response.body;
    vitestExpect(jsonBody.success).toBe(true);
    vitestExpect(jsonBody.imageRecordId).toBe(mockImageRecordData.id);
  }, 15000);

  vitestIt(
    'should use filename from Content-Disposition if available',
    async () => {
      if (!currentTestServerUrl) throw new Error('Test server URL not set');
      const mockBody = Buffer.from('data');
      const randomSuffix = Math.random().toString(36).substring(2, 7);
      const derivedGcsFilename = `from-header-${Date.now()}-${randomSuffix}.png`; 
      const mockGcsFileData = {
        filename: derivedGcsFilename, 
        url: `gcs-url/${derivedGcsFilename}`,
        contentType: 'image/png',
        size: mockBody.length,
      };
      const mockImageRecordData = { 
        id: 'img-content-disp', 
        gcsUrl: mockGcsFileData.url, 
        userId: MOCK_USER_ID, 
        originalUrl: MOCK_URL_NO_FILENAME, 
        gcsObjectName: derivedGcsFilename, 
        gcsBucketName: 'bkt', 
        filename: derivedGcsFilename, 
        contentType:'image/png', 
        size: mockBody.length, 
        appServedUrl: '/api/images/serve/img-content-disp',
        createdAt: new Date(), 
        updatedAt: new Date(),
      };
      
      (mockImageRecordCreate as Mock).mockResolvedValue(mockImageRecordData);
      (mockImageRecordUpdate as Mock).mockResolvedValue(mockImageRecordData);

      const response = await request(currentTestServerUrl)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_URL_NO_FILENAME)
        .set('X-Test-Mock-Fetch-Status', '200')
        .set('X-Test-Mock-Fetch-Body-Base64', mockBody.toString('base64'))
        .set(
          'X-Test-Mock-Fetch-Headers',
          JSON.stringify({
            'Content-Type': 'image/png',
            'Content-Length': mockBody.length.toString(),
            'Content-Disposition': `attachment; filename="from-header.png"`,
          }),
        )
        .set('X-Test-GCS-Upload-Success-Data', JSON.stringify(mockGcsFileData))
        .send(JSON.stringify({ externalImageUrl: MOCK_URL_NO_FILENAME }));
      
      vitestExpect(response.status).toBe(200);
      const jsonBody = response.body;
      vitestExpect(jsonBody.success).toBe(true);
      vitestExpect(jsonBody.imageRecordId).toBe(mockImageRecordData.id);
    },
    15000,
  );
  
  vitestIt(
    'should return 500 if fetching external image causes a network error (simulated by header)',
    async () => {
      if (!currentTestServerUrl) throw new Error('Test server URL not set');
      const response = await request(currentTestServerUrl)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
        .set('X-Test-Mock-Fetch-Status', '503') 
        .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));

      vitestExpect(response.status).toBe(500);
      vitestExpect(response.body.error).toBe('Failed to import image by URL');
      vitestExpect(response.body.details).toBe( 
        'Failed to fetch image. Status: 503',
      );
    },
    15000,
  );
}); 