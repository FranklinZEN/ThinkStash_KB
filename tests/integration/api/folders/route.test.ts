import { GET } from '@/app/api/folders/route'; // Import the handler
import { prisma } from '@/lib/prisma'; // Import prisma to mock
import { getCurrentUserId } from '@/lib/sessionUtils'; // Import session util to mock
import { NextResponse } from 'next/server';
import { NextRequest } from 'next/server';
import { POST } from '@/app/api/folders/route'; // Import POST handler
import { Prisma } from '@prisma/client'; // Import Prisma for error codes

// Mock dependencies
jest.mock('@/lib/prisma', () => ({
  prisma: {
    folder: {
      findMany: jest.fn(),
      findUnique: jest.fn(), // Mock for parent check
      create: jest.fn(),     // Mock for create
    },
  },
}));

jest.mock('@/lib/sessionUtils', () => ({
  getCurrentUserId: jest.fn(),
}));

// Mock NextRequest if necessary (often not needed for simple GET)
// const mockRequest = {} as NextRequest;

describe('GET /api/folders', () => {
  beforeEach(() => {
    // Reset mocks before each test
    jest.clearAllMocks();
  });

  it('should return 401 if user is not authenticated', async () => {
    (getCurrentUserId as jest.Mock).mockResolvedValue(null);

    const response = await GET(new Request('http://localhost/api/folders'));

    expect(response.status).toBe(401);
    const body = await response.json();
    expect(body.error).toBe('Unauthorized');
    expect(prisma.folder.findMany).not.toHaveBeenCalled();
  });

  it('should return an empty array if user has no folders', async () => {
    const mockUserId = 'user-123';
    (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
    (prisma.folder.findMany as jest.Mock).mockResolvedValue([]);

    const response = await GET(new Request('http://localhost/api/folders'));

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body).toEqual([]);
    expect(prisma.folder.findMany).toHaveBeenCalledWith({
      where: { userId: mockUserId },
      select: {
        id: true,
        name: true,
        parentId: true,
        updatedAt: true,
      },
      orderBy: {
        name: 'asc',
      },
    });
  });

  it('should return a flat list of folders for the authenticated user', async () => {
    const mockUserId = 'user-123';
    const mockFolders = [
      { id: 'f1', name: 'Folder A', parentId: null, updatedAt: new Date() },
      { id: 'f2', name: 'Folder B', parentId: 'f1', updatedAt: new Date() },
    ];
    (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
    (prisma.folder.findMany as jest.Mock).mockResolvedValue(mockFolders);

    const response = await GET(new Request('http://localhost/api/folders'));

    expect(response.status).toBe(200);
    const body = await response.json();
    // Dates need careful comparison or serialization check
    expect(body).toHaveLength(2);
    expect(body[0].id).toBe(mockFolders[0].id);
    expect(body[1].name).toBe(mockFolders[1].name);
    expect(prisma.folder.findMany).toHaveBeenCalledTimes(1);
  });

  it('should return 500 if there is a database error', async () => {
    const mockUserId = 'user-123';
    (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
    const dbError = new Error('Database connection failed');
    (prisma.folder.findMany as jest.Mock).mockRejectedValue(dbError);

    const response = await GET(new Request('http://localhost/api/folders'));

    expect(response.status).toBe(500);
    const body = await response.json();
    expect(body.error).toBe('Internal Server Error');
  });
});

describe('API /api/folders', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // --- POST Tests ---
  describe('POST', () => {
    const mockUserId = 'user-post-123';

    it('should return 401 if user is not authenticated', async () => {
      (getCurrentUserId as jest.Mock).mockResolvedValue(null);
      const request = new Request('http://localhost/api/folders', {
        method: 'POST',
        body: JSON.stringify({ name: 'New Folder' })
      });
      const response = await POST(request);
      expect(response.status).toBe(401);
      expect(prisma.folder.create).not.toHaveBeenCalled();
    });

    it('should return 400 if name is missing or invalid', async () => {
      (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
      const request = new Request('http://localhost/api/folders', {
        method: 'POST',
        body: JSON.stringify({ name: '   ' }) // Invalid name
      });
      const response = await POST(request);
      expect(response.status).toBe(400);
      const body = await response.json();
      expect(body.errors?.name).toBeDefined(); // Check Zod error structure
    });

    it('should return 400 if parentId is provided but invalid format', async () => {
      (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
      const request = new Request('http://localhost/api/folders', {
        method: 'POST',
        body: JSON.stringify({ name: 'Subfolder', parentId: 'invalid-cuid' })
      });
      const response = await POST(request);
      expect(response.status).toBe(400);
      const body = await response.json();
      expect(body.errors?.parentId).toBeDefined();
    });

    it('should return 400 if parent folder is not found or not owned by user', async () => {
      const parentId = 'non-existent-parent-id';
      (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(null); // Simulate parent not found

      const request = new Request('http://localhost/api/folders', {
        method: 'POST',
        body: JSON.stringify({ name: 'Subfolder', parentId: parentId })
      });
      const response = await POST(request);
      expect(response.status).toBe(400);
      const body = await response.json();
      expect(body.error).toContain('Parent folder not found');
      expect(prisma.folder.findUnique).toHaveBeenCalledWith({
        where: { id: parentId, userId: mockUserId },
        select: { id: true },
      });
    });

    it('should create a root folder successfully', async () => {
      const folderName = 'My Root Folder';
      const mockCreatedFolder = { id: 'new-folder-id', name: folderName, parentId: null, userId: mockUserId };
      (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
      (prisma.folder.create as jest.Mock).mockResolvedValue(mockCreatedFolder);

      const request = new Request('http://localhost/api/folders', {
        method: 'POST',
        body: JSON.stringify({ name: folderName, parentId: null })
      });
      const response = await POST(request);
      expect(response.status).toBe(201);
      const body = await response.json();
      expect(body).toEqual(mockCreatedFolder);
      expect(prisma.folder.create).toHaveBeenCalledWith({
        data: { name: folderName, parentId: null, userId: mockUserId },
      });
    });

    it('should create a subfolder successfully', async () => {
      const parentId = 'parent-folder-id';
      const folderName = 'My Subfolder';
      const mockParentFolder = { id: parentId, userId: mockUserId };
      const mockCreatedFolder = { id: 'new-subfolder-id', name: folderName, parentId: parentId, userId: mockUserId };

      (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
      (prisma.folder.findUnique as jest.Mock).mockResolvedValue(mockParentFolder); // Parent check passes
      (prisma.folder.create as jest.Mock).mockResolvedValue(mockCreatedFolder);

      const request = new Request('http://localhost/api/folders', {
        method: 'POST',
        body: JSON.stringify({ name: folderName, parentId: parentId })
      });
      const response = await POST(request);
      expect(response.status).toBe(201);
      const body = await response.json();
      expect(body).toEqual(mockCreatedFolder);
      expect(prisma.folder.create).toHaveBeenCalledWith({
        data: { name: folderName, parentId: parentId, userId: mockUserId },
      });
    });

    it('should return 409 if folder name already exists at the same level', async () => {
      const folderName = 'Duplicate Folder';
      (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
      const conflictError = new Prisma.PrismaClientKnownRequestError(
        'Unique constraint failed', 
        { code: 'P2002', clientVersion: 'test' }
      );
      (prisma.folder.create as jest.Mock).mockRejectedValue(conflictError);

      const request = new Request('http://localhost/api/folders', {
        method: 'POST',
        body: JSON.stringify({ name: folderName, parentId: null })
      });
      const response = await POST(request);
      expect(response.status).toBe(409);
      const body = await response.json();
      expect(body.error).toContain('already exists at this level');
    });

     it('should return 500 for other database errors during creation', async () => {
       const folderName = 'Error Folder';
       (getCurrentUserId as jest.Mock).mockResolvedValue(mockUserId);
       const dbError = new Error('Some other DB error');
       (prisma.folder.create as jest.Mock).mockRejectedValue(dbError);

       const request = new Request('http://localhost/api/folders', {
         method: 'POST',
         body: JSON.stringify({ name: folderName, parentId: null })
       });
       const response = await POST(request);
       expect(response.status).toBe(500);
       const body = await response.json();
       expect(body.error).toBe('Internal Server Error');
     });

  });
}); 