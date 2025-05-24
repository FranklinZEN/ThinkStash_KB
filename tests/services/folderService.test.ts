/**
 * @vitest-environment node
 */
import {
  getFoldersLogic,
  createFolderLogic,
  CreateFolderInput,
  FolderBasicDetails,
} from '@/lib/services/folderService';
import { Prisma } from '@prisma/client'; 
import { vi } from 'vitest';

import {
  mockFolderFindMany,
  mockFolderFindUnique,
  mockFolderCreate,
} from '@/tests/helpers/apiTestSetup';

const MOCK_USER_ID = 'user-folder-test-123';

describe('folderService', () => {
  beforeEach(() => {
    mockFolderFindMany.mockReset();
    mockFolderFindUnique.mockReset();
    mockFolderCreate.mockReset();
  });

  // --- Tests for getFoldersLogic ---
  describe('getFoldersLogic', () => {
    it('should return a list of folders for a user', async () => {
      const mockFolders: FolderBasicDetails[] = [
        { id: 'f1', name: 'Folder 1', parentId: null, updatedAt: new Date(), _count: { cards: 1 } },
        { id: 'f2', name: 'Folder 2', parentId: 'f1', updatedAt: new Date(), _count: { cards: 0 } },
      ];
      mockFolderFindMany.mockResolvedValue(mockFolders);
      const result = await getFoldersLogic(MOCK_USER_ID);
      expect(mockFolderFindMany).toHaveBeenCalledWith({
        where: { userId: MOCK_USER_ID },
        select: expect.any(Object),
        orderBy: { name: 'asc' },
      });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockFolders);
      expect(result.status).toBe(200);
    });

    it('should return an empty list if user has no folders', async () => {
      mockFolderFindMany.mockResolvedValue([]);
      const result = await getFoldersLogic(MOCK_USER_ID);
      expect(result.success).toBe(true);
      expect(result.data).toEqual([]);
      expect(result.status).toBe(200);
    });

    it('should return 500 status and error on Prisma findMany failure', async () => {
      mockFolderFindMany.mockRejectedValue(new Error('DB findMany error'));
      const result = await getFoldersLogic(MOCK_USER_ID);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to retrieve folders.');
      expect(result.status).toBe(500);
    });
  });

  // --- Tests for createFolderLogic ---
  describe('createFolderLogic', () => {
    const validInput: CreateFolderInput = {
      userId: MOCK_USER_ID,
      name: 'New Root Folder',
    };

    it('should create a root folder successfully', async () => {
      const createdFolder = { id: 'new-folder-id', ...validInput, parentId: null };
      mockFolderCreate.mockResolvedValue(createdFolder);
      mockFolderFindUnique.mockResolvedValue(null); 

      const result = await createFolderLogic(validInput);
      expect(mockFolderFindUnique).not.toHaveBeenCalled();
      expect(mockFolderCreate).toHaveBeenCalledWith({
        data: { name: validInput.name, parentId: validInput.parentId, userId: validInput.userId },
        select: expect.any(Object),
      });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(createdFolder);
      expect(result.status).toBe(201);
    });

    it('should create a subfolder successfully if parent exists and is owned by user', async () => {
      const parentFolderId = 'parent-id-123';
      const inputWithParent: CreateFolderInput = { ...validInput, name: 'New Subfolder', parentId: parentFolderId };
      const createdSubfolder = { id: 'new-subfolder-id', ...inputWithParent };

      mockFolderFindUnique.mockResolvedValue({ id: parentFolderId }); 
      mockFolderCreate.mockResolvedValue(createdSubfolder);
      const result = await createFolderLogic(inputWithParent);
      expect(mockFolderFindUnique).toHaveBeenCalledWith({
        where: { id: parentFolderId, userId: MOCK_USER_ID },
        select: { id: true },
      });
      expect(mockFolderCreate).toHaveBeenCalledWith({
        data: { name: inputWithParent.name, parentId: parentFolderId, userId: MOCK_USER_ID },
        select: expect.any(Object),
      });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(createdSubfolder);
      expect(result.status).toBe(201);
    });

    it('should return 400 if parent folder is not found', async () => {
      const parentFolderId = 'non-existent-parent-id';
      const inputWithParent: CreateFolderInput = { ...validInput, parentId: parentFolderId };
      mockFolderFindUnique.mockResolvedValue(null); 
      const result = await createFolderLogic(inputWithParent);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Parent folder not found or not owned by user.');
      expect(result.status).toBe(400);
      expect(mockFolderCreate).not.toHaveBeenCalled();
    });

    it('should return 409 for duplicate folder name (Prisma P2002 error)', async () => {
      const prismaError = new Prisma.PrismaClientKnownRequestError('Unique constraint failed', { code: 'P2002', clientVersion: 'mock' });
      mockFolderCreate.mockRejectedValue(prismaError);
      const result = await createFolderLogic(validInput);
      expect(result.success).toBe(false);
      expect(result.error).toBe('A folder with this name already exists at this level.');
      expect(result.status).toBe(409);
    });

    it('should return 500 for other Prisma create failures', async () => {
      mockFolderCreate.mockRejectedValue(new Error('Other DB create error'));
      const result = await createFolderLogic(validInput);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to create folder.');
      expect(result.details).toBe('Other DB create error');
      expect(result.status).toBe(500);
    });

    it('should return 500 if parent check fails for other reasons', async () => {
      const parentFolderId = 'parent-id-fail';
      const inputWithParent: CreateFolderInput = { ...validInput, parentId: parentFolderId };
      mockFolderFindUnique.mockRejectedValue(new Error('DB findUnique error for parent'));
      const result = await createFolderLogic(inputWithParent);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to create folder.');
      expect(result.details).toBe('DB findUnique error for parent');
      expect(result.status).toBe(500);
      expect(mockFolderCreate).not.toHaveBeenCalled();
    });
  });
}); 