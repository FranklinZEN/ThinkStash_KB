/**
 * @vitest-environment node
 */
import request from 'supertest';
import { makeTestServer, TestServer } from '@/tests/helpers/testServer';
import {
  MOCK_USER_ID,
  mockFolderFindMany,
  mockFolderCreate,
  mockFolderFindUnique,
  mockFolderDeleteMany,
  mockUserDeleteMany,
  mockUserCreate,
  mockFolderUpdate, // Ensure this is imported if used
  mockUserFindUnique // Ensure this is imported if used
} from '@/tests/helpers/apiTestSetup'; // USE ALIAS
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll, Mock } from 'vitest';

let currentTestServerUrl: string;
let testServerInstance: TestServer;

beforeAll(async () => {
  console.log('[folders/route.test.ts beforeAll] Starting test server...');
  testServerInstance = await makeTestServer(); 
  currentTestServerUrl = testServerInstance.url;
  console.log(`[folders/route.test.ts beforeAll] Test server started on ${currentTestServerUrl}`);

  // Initial mock setup from before, can be consolidated if this beforeEach is too crowded
  mockFolderFindMany.mockReset();
  mockFolderCreate.mockReset();
  mockFolderFindUnique.mockReset();
  mockFolderDeleteMany.mockReset(); 
  mockFolderUpdate.mockReset();
  mockUserDeleteMany.mockReset();   
  mockUserCreate.mockReset();       
  mockUserFindUnique.mockReset();

  (mockFolderDeleteMany as Mock).mockResolvedValue({ count: 0 });
  (mockUserDeleteMany as Mock).mockResolvedValue({ count: 0 });
  (mockUserCreate as Mock).mockImplementation(async (args: any) => args.data );
  (mockFolderFindUnique as Mock).mockResolvedValue(null); // Default for parent check

  const prismaMock = (globalThis as any).__PRISMA_INSTANCE__;
  if (!prismaMock) throw new Error('__PRISMA_INSTANCE__ not found on globalThis in beforeAll for folder tests');
  await prismaMock.folder.deleteMany({}); 
  await prismaMock.user.deleteMany({});   
  await prismaMock.user.create({        
    data: {
      id: MOCK_USER_ID,
      email: `${MOCK_USER_ID}@example.com`, 
      password: 'testpassword', 
      name: 'Mock Folders Test User',
    },
  });
});

afterAll(async () => {
  if (testServerInstance && testServerInstance.close) {
    console.log('[folders/route.test.ts afterAll] Closing test server...');
    await testServerInstance.close();
    console.log('[folders/route.test.ts afterAll] Test server closed.');
  }
});

describe('Folder API Route Handlers /api/folders', () => {
  beforeEach(() => {
    // Only mock resets that are specific to individual tests IF NOT COVERED by beforeAll resets
    // For instance, if a test changes mockFolderFindUnique, reset it here.
    // For now, vi.restoreAllMocks() in afterEach should handle most Vitest mock resets.
    // The explicit .mockReset() in beforeAll handles our shared mocks initial state.
    mockFolderFindMany.mockReset(); // Ensure it's clean for each GET test
    mockFolderCreate.mockReset();   // Ensure it's clean for each POST test
    mockFolderFindUnique.mockReset(); // Reset for tests that rely on its default or change it
  });

  afterEach(() => {
    vi.restoreAllMocks(); 
  });

  describe('GET /api/folders', () => {
    it('should return 401 if user is not authenticated', async () => {
      const response = await request(currentTestServerUrl).get('/api/folders').set('X-Test-User-Id', 'null'); 
      expect(response.status).toBe(401);
      expect(mockFolderFindMany).not.toHaveBeenCalled();
    });

    it('should call prisma.folder.findMany and return its success response', async () => {
      // console.log(`[[FOLDERS TEST DEBUG]] About to call GET /api/folders for findMany success. URL: ${currentTestServerUrl}`);
      const serviceResponseData = [
        { id: 'f1', name: 'Folder1', parentId: null, userId: MOCK_USER_ID, updatedAt: new Date(), _count: { cards: 0 } },
        { id: 'f2', name: 'Folder2', parentId: null, userId: MOCK_USER_ID, updatedAt: new Date(), _count: { cards: 3 } },
      ];
      (mockFolderFindMany as Mock).mockResolvedValue(serviceResponseData);
      const response = await request(currentTestServerUrl).get('/api/folders').set('X-Test-User-Id', MOCK_USER_ID);
      expect(response.status).toBe(200);
      expect(response.body).toEqual(serviceResponseData.map(f => ({...f, updatedAt: f.updatedAt.toISOString() })));
      expect(mockFolderFindMany).toHaveBeenCalledWith(expect.objectContaining({
        where: { userId: MOCK_USER_ID },
        orderBy: { name: 'asc' },
        select: expect.objectContaining({ _count: expect.any(Object) })
      }));
    });

    it('should return 500 if prisma.folder.findMany throws an error', async () => {
      (mockFolderFindMany as Mock).mockRejectedValue(new Error('Prisma DB error on findMany'));
      const response = await request(currentTestServerUrl).get('/api/folders').set('X-Test-User-Id', MOCK_USER_ID);
      expect(response.status).toBe(500);
      expect(response.body.error).toBe('Failed to retrieve folders.');
    });
  });

  describe('POST /api/folders', () => {
    it('should return 401 if user is not authenticated', async () => {
      const payload = { name: 'Test Folder' };
      const response = await request(currentTestServerUrl)
        .post('/api/folders')
        .set('X-Test-User-Id', 'null')
        .set('Content-Type', 'application/json')
        .send(JSON.stringify(payload)); // No need for .set('Accept', 'application/json') with supertest
      expect(response.status).toBe(401);
      expect(mockFolderCreate).not.toHaveBeenCalled();
    });

    it('should return 400 for invalid request body (e.g. missing name)', async () => {
      const payload = { parentId: 'abc' }; 
      const response = await request(currentTestServerUrl)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify(payload));
      expect(response.status).toBe(400);
      expect(mockFolderCreate).not.toHaveBeenCalled();
    });

    it('should call prisma.folder.create and return success (no parentId)', async () => {
      const folderName = 'New Unique Folder';
      const payload = { name: folderName, parentId: null };
      const mockDbResponse = { id: 'new-folder-id-123', name: folderName, parentId: null, userId: MOCK_USER_ID }; 
      (mockFolderCreate as Mock).mockResolvedValue(mockDbResponse);
      const response = await request(currentTestServerUrl)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify(payload));
      expect(response.status).toBe(201);
      expect(response.body).toEqual(mockDbResponse);
      expect(mockFolderCreate).toHaveBeenCalledWith({
        data: { userId: MOCK_USER_ID, name: folderName, parentId: null },
        select: { id: true, name: true, parentId: true, userId: true },
      });
      expect(mockFolderFindUnique).not.toHaveBeenCalled();
    });

    it('should call prisma.folder.create and return success (with valid parentId)', async () => {
      const folderName = 'New Sub Folder';
      const parentFolderId = 'clxkjm7k9000008l7c356f0a1'; 
      const payload = { name: folderName, parentId: parentFolderId };
      const mockDbResponse = { id: 'new-subfolder-id-456', name: folderName, parentId: parentFolderId, userId: MOCK_USER_ID }; 
      (mockFolderCreate as Mock).mockResolvedValue(mockDbResponse);
      (mockFolderFindUnique as Mock).mockResolvedValue({ id: parentFolderId, userId: MOCK_USER_ID }); 
      const response = await request(currentTestServerUrl)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify(payload));
      expect(response.status).toBe(201);
      expect(response.body).toEqual(mockDbResponse);
      expect(mockFolderFindUnique).toHaveBeenCalledWith({ where: { id: parentFolderId, userId: MOCK_USER_ID }, select: { id: true } });
      expect(mockFolderCreate).toHaveBeenCalledWith({
        data: { userId: MOCK_USER_ID, name: folderName, parentId: parentFolderId },
        select: { id: true, name: true, parentId: true, userId: true },
      });
    });

    it('should return 400 if parentId is provided but parent folder not found/owned', async () => {
      const folderName = 'New Sub Folder Fail';
      const parentFolderId = 'clxkjm7k9000008l7c356f0a2'; 
      const payload = { name: folderName, parentId: parentFolderId };
      (mockFolderFindUnique as Mock).mockResolvedValue(null); 
      const response = await request(currentTestServerUrl)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify(payload));
      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Parent folder not found or not owned by user.');
      expect(mockFolderFindUnique).toHaveBeenCalledWith({ where: { id: parentFolderId, userId: MOCK_USER_ID }, select: { id: true } });
      expect(mockFolderCreate).not.toHaveBeenCalled();
    });

    it('should return 409 if prisma.folder.create throws a P2002 error', async () => {
      const folderName = 'Existing Folder Name';
      const payload = { name: folderName, parentId: null };
      const errorInstance = new Error('Unique constraint failed on fields: (`name`, `parentId`, `userId`)');
      (errorInstance as any).code = 'P2002';
      (errorInstance as any).name = 'PrismaClientKnownRequestError';
      (mockFolderCreate as Mock).mockRejectedValue(errorInstance);
      const response = await request(currentTestServerUrl)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify(payload));
      expect(response.status).toBe(409);
      expect(response.body.error).toBe('A folder with this name already exists at this level.');
    });

    it('should return 500 if prisma.folder.create throws an unexpected error', async () => {
      const folderName = 'Another Folder';
      const payload = { name: folderName, parentId: null };
      (mockFolderCreate as Mock).mockRejectedValue(new Error('Unexpected DB error on create'));
      const response = await request(currentTestServerUrl)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .send(JSON.stringify(payload));
      expect(response.status).toBe(500);
      expect(response.body.error).toBe('Failed to create folder.'); 
    });
  });
}); 