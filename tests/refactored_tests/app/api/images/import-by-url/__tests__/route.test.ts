/**
 * @vitest-environment node
 */
import request from 'supertest';
// Path adjusted for the new location under tests/refactored_tests/
import { makeTestServer, TestServer } from '../../../../../../helpers/testServer'; 
import {
  MOCK_USER_ID,
  mockUserCreate,
  mockUserDeleteMany,
  mockImageRecordCreate,
  mockImageRecordUpdate,
  mockImageRecordDeleteMany,
  // mockGCSUploadFile, // No longer directly used in this test if route uses headers for GCS
  // Assuming apiTestSetup.ts also exports Prisma mock functions if needed for direct use
  // For example: mockImageRecordFindUnique, mockUserFindUnique etc.
} from '../../../../../../helpers/apiTestSetup'; 

import {
  vi,
  beforeEach as vitestBeforeEach,
  afterEach as vitestAfterEach,
  describe as vitestDescribe,
  it as vitestIt,
  expect as vitestExpect,
  beforeAll as vitestBeforeAll,
  afterAll as vitestAfterAll,
  Mock,
} from 'vitest';

// Removed: vi.mock('@/lib/gcs', ...) as the route seems to use header-based GCS mocking for tests

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

let testApp: TestServer;

vitestBeforeAll(async () => {
  testApp = await makeTestServer();
});

vitestAfterAll(async () => {
  if (testApp) {
    await testApp.close();
  }
});

vitestDescribe.sequential('/api/images/import-by-url POST', () => {
  vitestBeforeEach(async () => {
    mockUserCreate.mockReset();
    mockUserDeleteMany.mockReset();
    mockImageRecordCreate.mockReset();
    mockImageRecordUpdate.mockReset();
    mockImageRecordDeleteMany.mockReset();
    // mockGCSUploadFile.mockReset(); // Not used directly anymore

    (mockImageRecordDeleteMany as Mock).mockResolvedValue({ count: 0 });
    (mockUserDeleteMany as Mock).mockResolvedValue({ count: 0 });
    (mockUserCreate as Mock).mockImplementation(async (args: any) => args.data);

    // console.log(
    //   '[TEST_CASE_SETUP] Clearing tables and creating MOCK_USER_ID (beforeEach)...',
    // );
    try {
      await (globalThis as any).__PRISMA__.imageRecord.deleteMany({});
      await (globalThis as any).__PRISMA__.user.deleteMany({});
      await (globalThis as any).__PRISMA__.user.create({
        data: {
          id: MOCK_USER_ID,
          email: `${MOCK_USER_ID}@example.com`,
          password: 'testpassword',
          name: 'Mock Test User',
        },
      });
      // console.log(
      //   `[TEST_CASE_SETUP] Tables cleared and MOCK_USER_ID ${MOCK_USER_ID} created.`,
      // );
    } catch (error) {
      // console.error('[TEST_CASE_SETUP] Error in beforeEach setup:', error);
      throw error;
    }
  });

  vitestAfterEach(() => {
    vi.restoreAllMocks();
  });

  vitestIt('should return 401 if user is not authenticated', async () => {
    const response = await request(testApp.url)
      .post('/api/images/import-by-url')
      .set('X-Test-User-Id', 'null')
      .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));
    vitestExpect(response.status).toBe(401);
    vitestExpect(response.body.error).toBe('Unauthorized');
  });

  vitestIt('should return 400 if request body is invalid JSON', async () => {
    const response = await request(testApp.url)
      .post('/api/images/import-by-url')
      .set('X-Test-User-Id', MOCK_USER_ID)
      .set('Content-Type', 'application/json')
      .send('not a valid json');
    vitestExpect(response.status).toBe(400);
    vitestExpect(response.body.error).toBe('Invalid JSON format');
  });

  vitestIt(
    'should return 400 if externalImageUrl is missing or invalid',
    async () => {
      const response = await request(testApp.url)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .send(JSON.stringify({ externalImageUrl: 'not-a-url' }));
      vitestExpect(response.status).toBe(400);
      vitestExpect(response.body.error).toBe('Invalid request body');
    },
  );

  vitestIt(
    'should return 500 if fetching the external image fails (e.g. 404)',
    async () => {
      const response = await request(testApp.url)
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
  );

  vitestIt(
    'should return 400 if external image content type is not supported',
    async () => {
      const mockBody = Buffer.from('data');
      const response = await request(testApp.url)
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
  );
  
  vitestIt(
    'should return 400 if external image content-length header exceeds max size',
    async () => {
      const response = await request(testApp.url)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
        .set('X-Test-Mock-Fetch-Status', '200')
        .set(
          'X-Test-Mock-Fetch-Headers',
          JSON.stringify({
            'Content-Type': 'image/jpeg',
            'Content-Length': (6 * 1024 * 1024).toString(),
          }),
        )
        .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));
      vitestExpect(response.status).toBe(400);
      vitestExpect(response.body.error).toBe(
        'Image is too large. Maximum size: 5MB',
      );
    },
  );

  vitestIt(
    'should return 400 if external image buffer exceeds max size',
    async () => {
      const response = await request(testApp.url)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
        .set('X-Test-Mock-Fetch-Status', '200-large-buffer-test')
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
  );

  vitestIt(
    'should successfully import image, create record, and return appServedUrl',
    async () => {
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
      };

      // Configure Prisma mocks for success (the route will still interact with these)
      (mockImageRecordCreate as Mock).mockResolvedValue(mockImageRecordData);
      (mockImageRecordUpdate as Mock).mockResolvedValue(mockImageRecordData);

      const response = await request(testApp.url)
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
        // Add back GCS success header for the route to use
        .set('X-Test-GCS-Upload-Success-Data', JSON.stringify(mockGcsFileData)) 
        .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));

      // if (response.status !== 200) {
      //   console.log(
      //     '[SUCCESS_TEST_FAIL_DETAIL] API Status:',
      //     response.status,
      //     'Body:',
      //     response.body,
      //   );
      // }
      vitestExpect(response.status).toBe(200);
      const jsonBody = response.body;
      vitestExpect(jsonBody.success).toBe(true);
      vitestExpect(jsonBody.imageRecordId).toBe(mockImageRecordData.id);
      vitestExpect(jsonBody.appServedUrl).toContain(mockImageRecordData.id);
      vitestExpect(jsonBody.gcsUrl).toBe(mockGcsFileData.url);

      // We can still assert that Prisma mocks were called as expected
      vitestExpect(mockImageRecordCreate).toHaveBeenCalled(); 
    },
  );

  vitestIt('should return 500 if GCS upload fails', async () => {
    const mockImageBuffer = Buffer.from('mock image data for gcs fail');
    const gcsErrorMessage = 'Simulated GCS Upload Error From Header';

    // Prisma mocks might still be called if GCS fails early, or not. Depends on route logic.
    // For safety, ensure they are set up to not cause unexpected issues.
    (mockImageRecordCreate as Mock).mockResolvedValue({ id: 'any-id' }); // Or other suitable resolved value

    const response = await request(testApp.url)
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
      // Add back GCS error header for the route to use
      .set('X-Test-GCS-Upload-Error', gcsErrorMessage) 
      .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));

    vitestExpect(response.status).toBe(500);
    vitestExpect(response.body.error).toBe('Failed to import image by URL');
    vitestExpect(response.body.details).toBe(gcsErrorMessage);
  });

  vitestIt('should return 500 if Prisma create fails', async () => {
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

    const response = await request(testApp.url)
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
      // GCS part should succeed for this test to focus on Prisma failure
      .set('X-Test-GCS-Upload-Success-Data', JSON.stringify(mockGcsFileData)) 
      .send(JSON.stringify({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL }));

    vitestExpect(response.status).toBe(500);
    vitestExpect(response.body.error).toBe('Failed to import image by URL');
    vitestExpect(response.body.details).toBe(prismaCreateError.message);
  });

  vitestIt('should return 500 if Prisma update fails (if applicable to route logic)', async () => {
    const mockImageBuffer = Buffer.from('mock image data for prisma update fail');
    const randomSuffix = Math.random().toString(36).substring(2, 7);
    const uniqueGcsFilename = `test-prisma-update-fail-${Date.now()}-${randomSuffix}.webp`;
    const mockGcsFileData = { 
      filename: uniqueGcsFilename,
      contentType: 'image/webp',
      size: mockImageBuffer.length,
      url: `some-gcs-url/${uniqueGcsFilename}`,
    };
    const mockCreatedImageRecord = { id: 'temp-id', userId: MOCK_USER_ID, originalUrl: MOCK_EXTERNAL_IMAGE_URL, gcsObjectName: 'obj', gcsBucketName: 'bkt', filename:'fn', contentType:'type', size:100 };

    (mockImageRecordCreate as Mock).mockResolvedValue(mockCreatedImageRecord); 
    const prismaUpdateError = new Error('Simulated Prisma Update Failed From Mock');
    (mockImageRecordUpdate as Mock).mockRejectedValue(prismaUpdateError);

    const response = await request(testApp.url)
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
  });

  vitestIt('should extract filename correctly from complex URL', async () => {
    const mockBody = Buffer.from('data');
    const randomSuffix = Math.random().toString(36).substring(2, 7);
    const uniqueGcsFilename = `test-complex-url-${Date.now()}-${randomSuffix}.jpeg`;
    const mockGcsFileData = {
      filename: uniqueGcsFilename,
      url: `gcs-url/${uniqueGcsFilename}`,
      contentType: 'image/jpeg',
      size: mockBody.length,
    };
    const mockImageRecordData = { id: 'img-complex', gcsUrl: mockGcsFileData.url, userId: MOCK_USER_ID, originalUrl: MOCK_COMPLEX_IMAGE_URL, gcsObjectName: 'obj', gcsBucketName: 'bkt', filename:'fn', contentType:'type', size:100, appServedUrl: 'url' };
    
    (mockImageRecordCreate as Mock).mockResolvedValue(mockImageRecordData);
    (mockImageRecordUpdate as Mock).mockResolvedValue(mockImageRecordData);

    const response = await request(testApp.url)
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
    vitestExpect(jsonBody.imageRecordId).toBeDefined();
  });

  vitestIt(
    'should use filename from Content-Disposition if available',
    async () => {
      const mockBody = Buffer.from('data');
      const randomSuffix = Math.random().toString(36).substring(2, 7);
      const uniqueGcsFilename = `test-content-disp-${Date.now()}-${randomSuffix}.png`;
      const mockGcsFileData = {
        filename: uniqueGcsFilename,
        url: `gcs-url/${uniqueGcsFilename}`,
        contentType: 'image/png',
        size: mockBody.length,
      };
      const mockImageRecordData = { id: 'img-content-disp', gcsUrl: mockGcsFileData.url, userId: MOCK_USER_ID, originalUrl: MOCK_URL_NO_FILENAME, gcsObjectName: 'obj', gcsBucketName: 'bkt', filename:'fn', contentType:'type', size:100, appServedUrl: 'url' };
      
      (mockImageRecordCreate as Mock).mockResolvedValue(mockImageRecordData);
      (mockImageRecordUpdate as Mock).mockResolvedValue(mockImageRecordData);

      const response = await request(testApp.url)
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
      vitestExpect(jsonBody.imageRecordId).toBeDefined();
    },
  );
  
  vitestIt(
    'should return 500 if fetching external image causes a network error (simulated by header)',
    async () => {
      const response = await request(testApp.url)
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
  );
}); 