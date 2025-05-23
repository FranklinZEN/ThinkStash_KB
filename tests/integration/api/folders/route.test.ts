/**
 * @vitest-environment node
 */
import {
  MOCK_USER_ID, // Using the shared MOCK_USER_ID
  mockFolderFindMany,
  mockFolderCreate,
  mockFolderFindUnique,
  mockFolderDeleteMany,
  mockUserDeleteMany,
  mockUserCreate,
  mockFolderUpdate, // Ensure this is imported if used
  mockUserFindUnique // Ensure this is imported if used
} from '../../../helpers/apiTestSetup'; // Import centralized mocks and MOCK_USER_ID
import request from 'supertest';
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, Mock } from 'vitest'; // Mock type might not be needed here anymore if not casting
import { makeTestServer, TestServer } from '../../../helpers/testServer';

// Local vi.fn() declarations and vi.mock for @/lib/prisma are now removed, 
// as they are handled by apiTestSetup.ts

// ----- 3. Import the MOCKED prisma client AFTER vi.mock (handled by apiTestSetup) -----
// import prisma from '@/lib/prisma'; // No longer needed here due to global injection

// const MOCK_USER_ID_FOLDERS = 'cmazq680i0000u5z0dm3orlss'; // Replaced by MOCK_USER_ID from apiTestSetup
let testApp: TestServer;

beforeAll(async () => {
  testApp = await makeTestServer(); 
});

afterAll(async () => {
  if (testApp) { await testApp.close(); }
});

describe('Folder API Route Handlers /api/folders', () => {
  beforeEach(async () => {
    // Reset all top-level mock functions
    mockFolderFindMany.mockReset();
    mockFolderCreate.mockReset();
    mockFolderFindUnique.mockReset();
    mockFolderDeleteMany.mockReset(); 
    mockFolderUpdate.mockReset(); // Reset if used
    mockUserDeleteMany.mockReset();   
    mockUserCreate.mockReset();       
    mockUserFindUnique.mockReset(); // Reset if used

    // Configure mocks for beforeEach DB operations
    (mockFolderDeleteMany as Mock).mockResolvedValue({ count: 0 });
    (mockUserDeleteMany as Mock).mockResolvedValue({ count: 0 });
    (mockUserCreate as Mock).mockImplementation(async (args: any) => args.data ); // Simulate create returning input data
    
    // Default behavior for findUnique (called by createFolderLogic service)
    (mockFolderFindUnique as Mock).mockImplementation(async (args: any) => {
      if (args.where && args.where.id && args.where.id !== 'clxkjmsb0000108l71b20b2z7') { // Example of a non-existent ID for specific tests
        return { id: args.where.id, userId: MOCK_USER_ID };
      }
      return null;
    });

    // console.log('[TEST_CASE_SETUP /api/folders] Simulating DB cleanup and user creation via MOCKED Prisma (beforeEach)...');
    await (globalThis as any).__PRISMA__.folder.deleteMany({}); 
    await (globalThis as any).__PRISMA__.user.deleteMany({});   
    await (globalThis as any).__PRISMA__.user.create({        
      data: {
        id: MOCK_USER_ID, // Use MOCK_USER_ID from setup
        email: `${MOCK_USER_ID}@example.com`, 
        password: 'testpassword', 
        name: 'Mock Folders Test User',
      },
    });
    // console.log(`[TEST_CASE_SETUP /api/folders] DB operations simulated via mocks. MOCK_USER_ID ${MOCK_USER_ID} assumed created.`);
  });

  afterEach(() => {
    vi.restoreAllMocks(); 
  });

  describe('GET /api/folders', () => {
    it('should return 401 if user is not authenticated', async () => {
      const response = await request(testApp.url).get('/api/folders').set('X-Test-User-Id', 'null'); 
      expect(response.status).toBe(401);
      // Ensure we are using the imported mock
      expect(mockFolderFindMany).not.toHaveBeenCalled();
    });

    it('should call prisma.folder.findMany and return its success response', async () => {
      const serviceResponseData = [
        { id: 'f1', name: 'Folder1', parentId: null, userId: MOCK_USER_ID, updatedAt: new Date(), _count: { cards: 0 } }, // Use MOCK_USER_ID
        { id: 'f2', name: 'Folder2', parentId: null, userId: MOCK_USER_ID, updatedAt: new Date(), _count: { cards: 3 } }, // Use MOCK_USER_ID
      ];
      // Ensure we are using the imported mock
      (mockFolderFindMany as Mock).mockResolvedValue(serviceResponseData);
      const response = await request(testApp.url).get('/api/folders').set('X-Test-User-Id', MOCK_USER_ID); // Use MOCK_USER_ID
      expect(response.status).toBe(200);
      expect(response.body).toEqual(serviceResponseData.map(f => ({...f, updatedAt: f.updatedAt.toISOString() })));
      // Ensure we are using the imported mock
      expect(mockFolderFindMany).toHaveBeenCalledWith(expect.objectContaining({
        where: { userId: MOCK_USER_ID }, // Use MOCK_USER_ID
        orderBy: { name: 'asc' },
        select: expect.objectContaining({ _count: expect.any(Object) })
      }));
    });

    it('should return 500 if prisma.folder.findMany throws an error', async () => {
      // Ensure we are using the imported mock
      (mockFolderFindMany as Mock).mockRejectedValue(new Error('Prisma DB error on findMany'));
      const response = await request(testApp.url).get('/api/folders').set('X-Test-User-Id', MOCK_USER_ID); // Use MOCK_USER_ID
      expect(response.status).toBe(500);
      expect(response.body.error).toBe('Failed to retrieve folders.');
    });
  });

  describe('POST /api/folders', () => {
    it('should return 401 if user is not authenticated', async () => {
      const payload = { name: 'Test Folder' };
      const response = await request(testApp.url)
        .post('/api/folders')
        .set('X-Test-User-Id', 'null')
        .set('Content-Type', 'application/json')
        .set('Accept', 'application/json')
        .send(JSON.stringify(payload));
      expect(response.status).toBe(401);
      expect(mockFolderCreate).not.toHaveBeenCalled();
    });

    it('should return 400 for invalid request body (e.g. missing name)', async () => {
      const payload = { parentId: 'abc' }; // Name is missing, parentId is invalid CUID
      const response = await request(testApp.url)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .set('Accept', 'application/json')
        .send(JSON.stringify(payload));
      expect(response.status).toBe(400);
      expect(mockFolderCreate).not.toHaveBeenCalled();
    });

    it('should call prisma.folder.create and return success (no parentId)', async () => {
      const folderName = 'New Unique Folder';
      const payload = { name: folderName, parentId: null };
      const mockDbResponse = { id: 'new-folder-id-123', name: folderName, parentId: null, userId: MOCK_USER_ID }; 
      (mockFolderCreate as Mock).mockResolvedValue(mockDbResponse);
      const response = await request(testApp.url)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .set('Accept', 'application/json')
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
      const response = await request(testApp.url)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .set('Accept', 'application/json')
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
      const response = await request(testApp.url)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .set('Accept', 'application/json')
        .send(JSON.stringify(payload));
      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Parent folder not found or not owned by user.');
      expect(mockFolderFindUnique).toHaveBeenCalledWith({ where: { id: parentFolderId, userId: MOCK_USER_ID }, select: { id: true } });
      expect(mockFolderCreate).not.toHaveBeenCalled();
    });

    it('should return 409 if prisma.folder.create throws a P2002 error', async () => {
      const folderName = 'Existing Folder Name';
      const payload = { name: folderName, parentId: null };
      
      // Create an error object that more closely resembles PrismaClientKnownRequestError
      const errorInstance = new Error('Unique constraint failed on fields: (`name`, `parentId`, `userId`)'); // More specific message
      (errorInstance as any).code = 'P2002';
      (errorInstance as any).name = 'PrismaClientKnownRequestError'; // Crucial for some instanceof-like checks or type guards
      // (errorInstance as any).clientVersion = '5.0.0'; // Example, if needed
      // (errorInstance as any).meta = { target: ['name', 'parentId', 'userId'] }; // Example, if needed

      (mockFolderCreate as Mock).mockRejectedValue(errorInstance);
      
      const response = await request(testApp.url)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .set('Accept', 'application/json')
        .send(JSON.stringify(payload));
      expect(response.status).toBe(409);
      expect(response.body.error).toBe('A folder with this name already exists at this level.');
    });

    it('should return 500 if prisma.folder.create throws an unexpected error', async () => {
      const folderName = 'Another Folder';
      const payload = { name: folderName, parentId: null };
      (mockFolderCreate as Mock).mockRejectedValue(new Error('Unexpected DB error on create'));
      const response = await request(testApp.url)
        .post('/api/folders')
        .set('X-Test-User-Id', MOCK_USER_ID)
        .set('Content-Type', 'application/json')
        .set('Accept', 'application/json')
        .send(JSON.stringify(payload));
      expect(response.status).toBe(500);
      expect(response.body.error).toBe('Failed to create folder.'); 
    });
  });
});