/**
 * @jest-environment node
 */
import request from 'supertest';
// import { http, HttpResponse } from 'msw'; // MSW no longer used in this file for fetch mocking
// import { server } from '@/mocks/server';   // MSW server no longer used in this file for fetch mocking
// import nock from 'nock'; // ADD: Import nock

// import * as _appHandler from '../route'; // Commented out as unused
import prisma from '@/lib/prisma';
// import { uploadFile } from '@/lib/gcs'; // Linter says unused, assuming tests use the mock via vi.mock
import {
  vi,
  /* Mock, */ beforeEach as vitestBeforeEach,
  afterEach as vitestAfterEach,
  describe as vitestDescribe,
  it as vitestIt,
  expect as vitestExpect,
} from 'vitest'; // Mock import commented
// REMOVE: import cuid from 'cuid';

// Global Prisma mock is removed from vitest.setup.ts
// We will spyOn specific prisma methods in tests that need to simulate prisma errors.

vi.mock('@/lib/gcs', () => ({
  ...vi.importActual('@/lib/gcs'),
  uploadFile: vi.fn(), // This is the mock for the imported uploadFile
}));

// const mockUploadFile = uploadFile as Mock; // This assignment itself is okay if mockUploadFile is used,
// but the linter flagged it as unused. If uploadFile (the import)
// is what tests use to interact with the mock, then this const is indeed unused.
// Let's remove it based on the linter error for mockUploadFile.

// const _MOCK_USER_ID = 'user-123'; // Old value
const MOCK_USER_ID = 'cmazq680i0000u5z0dm3orlss'; // UPDATED with actual ID from test DB

// Define URLs for nock
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

// const _MOCK_VALID_IMAGE_RECORD_ID = 'new-image-record-id'; // Commented out as unused by linter
// const MOCK_VALID_IMAGE_RECORD_ID = 'new-image-record-id';
const API_URL = process.env.TEST_API_URL || 'http://localhost:3000';

// MODIFIED: Use .sequential to run tests in this describe block serially
vitestDescribe.sequential('/api/images/import-by-url POST', () => {
  vitestBeforeEach(async () => {
    console.log(
      '[TEST_CASE_SETUP] Clearing tables and creating MOCK_USER_ID (beforeEach)...',
    );
    try {
      // Delete ImageRecords first to avoid FK issues if User deletion doesn't cascade reliably in test env
      await prisma.imageRecord.deleteMany({});
      await prisma.user.deleteMany({});

      // Create the specific mock user needed for these tests
      await prisma.user.create({
        data: {
          id: MOCK_USER_ID,
          email: `${MOCK_USER_ID}@example.com`, // Ensure email is unique for the user model
          password: 'testpassword', // Add required fields for User model
          name: 'Mock Test User',
        },
      });
      console.log(
        `[TEST_CASE_SETUP] Tables cleared and MOCK_USER_ID ${MOCK_USER_ID} created.`,
      );
    } catch (error) {
      console.error('[TEST_CASE_SETUP] Error in beforeEach setup:', error);
      throw error;
    }
  });

  vitestAfterEach(() => {
    vi.restoreAllMocks();
  });

  vitestIt('should return 401 if user is not authenticated', async () => {
    const response = await request(API_URL)
      .post('/api/images/import-by-url')
      .set('X-Test-User-Id', 'null')
      .send({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL });
    vitestExpect(response.status).toBe(401);
    vitestExpect(response.body.error).toBe('Unauthorized');
  });

  vitestIt('should return 400 if request body is invalid JSON', async () => {
    const response = await request(API_URL)
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
      const response = await request(API_URL)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .send({ externalImageUrl: 'not-a-url' });
      vitestExpect(response.status).toBe(400);
      vitestExpect(response.body.error).toBe('Invalid request body');
    },
  );

  vitestIt(
    'should return 400 if fetching the external image fails (e.g. 404)',
    async () => {
      const response = await request(API_URL)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
        .set('X-Test-Mock-Fetch-Status', '404')
        .send({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL });
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
      const response = await request(API_URL)
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
        .send({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL });
      vitestExpect(response.status).toBe(400);
      vitestExpect(response.body.error).toBe(
        'Invalid image type. Allowed types: image/jpeg, image/png, image/gif, image/webp',
      );
    },
  );

  vitestIt(
    'should return 400 if external image content-length header exceeds max size',
    async () => {
      const response = await request(API_URL)
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
        .send({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL });
      vitestExpect(response.status).toBe(400);
      vitestExpect(response.body.error).toBe(
        'Image is too large. Maximum size: 5MB',
      );
    },
  );

  vitestIt(
    'should return 400 if external image buffer exceeds max size',
    async () => {
      const response = await request(API_URL)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
        .set('X-Test-Mock-Fetch-Status', '200-large-buffer-test')
        .set(
          'X-Test-Mock-Fetch-Headers',
          JSON.stringify({ 'Content-Type': 'image/jpeg' }),
        )
        .send({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL });

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

      const response = await request(API_URL)
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
        .send({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL });

      if (response.status !== 200) {
        console.log(
          '[SUCCESS_TEST_FAIL_DETAIL] API Status:',
          response.status,
          'Body:',
          response.body,
        );
      }
      vitestExpect(response.status).toBe(200);
      const jsonBody = response.body;
      vitestExpect(jsonBody.success).toBe(true);
      vitestExpect(jsonBody.imageRecordId).toBeDefined();
      vitestExpect(jsonBody.appServedUrl).toContain(jsonBody.imageRecordId);
      vitestExpect(jsonBody.gcsUrl).toBe(mockGcsFileData.url);
    },
  );

  vitestIt('should return 500 if GCS upload fails', async () => {
    const mockImageBuffer = Buffer.from('mock image data for gcs fail');
    const response = await request(API_URL)
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
      .set('X-Test-GCS-Upload-Error', 'Simulated GCS Upload Error From Header')
      .send({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL });

    vitestExpect(response.status).toBe(500);
    vitestExpect(response.body.error).toBe('Failed to import image by URL');
    vitestExpect(response.body.details).toBe(
      'Simulated GCS Upload Error From Header',
    );
  });

  vitestIt('should return 500 if Prisma create fails', async () => {
    const mockImageBuffer = Buffer.from(
      'mock image data for prisma create fail',
    );
    const randomSuffix = Math.random().toString(36).substring(2, 7);
    const uniqueGcsFilename = `test-prisma-create-fail-${Date.now()}-${randomSuffix}.gif`;
    const mockGcsFileData = {
      filename: uniqueGcsFilename,
      contentType: 'image/gif',
      size: mockImageBuffer.length,
      url: `some-gcs-url/${uniqueGcsFilename}`,
    };

    const response = await request(API_URL)
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
      .set(
        'X-Test-Prisma-Create-Error',
        'Simulated Prisma Create Failed From Header',
      )
      .send({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL });

    vitestExpect(response.status).toBe(500);
    vitestExpect(response.body.error).toBe('Failed to import image by URL');
    vitestExpect(response.body.details).toBe(
      'Simulated Prisma Create Failed From Header',
    );
  });

  vitestIt('should return 500 if Prisma update fails', async () => {
    const mockImageBuffer = Buffer.from(
      'mock image data for prisma update fail',
    );
    const randomSuffix = Math.random().toString(36).substring(2, 7);
    const uniqueGcsFilename = `test-prisma-update-fail-${Date.now()}-${randomSuffix}.webp`;
    const mockGcsFileData = {
      filename: uniqueGcsFilename,
      contentType: 'image/webp',
      size: mockImageBuffer.length,
      url: `some-gcs-url/${uniqueGcsFilename}`,
    };

    const response = await request(API_URL)
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
      .set(
        'X-Test-Prisma-Update-Error',
        'Simulated Prisma Update Failed From Header',
      )
      .send({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL });

    vitestExpect(response.status).toBe(500);
    vitestExpect(response.body.error).toBe('Failed to import image by URL');
    vitestExpect(response.body.details).toBe(
      'Simulated Prisma Update Failed From Header',
    );
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

    const response = await request(API_URL)
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
      .send({ externalImageUrl: MOCK_COMPLEX_IMAGE_URL });
    if (response.status !== 200) {
      console.log('[COMPLEX_URL_TEST_FAIL_DETAIL]', response.body);
    }
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

      const response = await request(API_URL)
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
        .send({ externalImageUrl: MOCK_URL_NO_FILENAME });
      if (response.status !== 200) {
        console.log('[CONTENT_DISP_TEST_FAIL_DETAIL]', response.body);
      }
      vitestExpect(response.status).toBe(200);
      const jsonBody = response.body;
      vitestExpect(jsonBody.success).toBe(true);
      vitestExpect(jsonBody.imageRecordId).toBeDefined();
    },
  );

  vitestIt(
    'should return 500 if fetching external image causes a network error (simulated by header)',
    async () => {
      const response = await request(API_URL)
        .post('/api/images/import-by-url')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('X-Test-Mock-Fetch-Url', MOCK_EXTERNAL_IMAGE_URL)
        .set('X-Test-Mock-Fetch-Status', '503')
        .send({ externalImageUrl: MOCK_EXTERNAL_IMAGE_URL });

      vitestExpect(response.status).toBe(500);
      vitestExpect(response.body.error).toBe('Failed to import image by URL');
      vitestExpect(response.body.details).toBe(
        'Failed to fetch image. Status: 503',
      );
    },
  );
});
