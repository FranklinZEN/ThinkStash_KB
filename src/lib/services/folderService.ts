import { Prisma, PrismaClient } from '@prisma/client';

// Define the shape of the Prisma subset needed by this service
export interface FolderPrismaSubset {
  folder: {
    findMany: PrismaClient['folder']['findMany'];
    findUnique: PrismaClient['folder']['findUnique'];
    create: PrismaClient['folder']['create'];
  };
}

export interface FolderBasicDetails {
  id: string;
  name: string;
  parentId: string | null;
  updatedAt: Date;
  _count?: {
    cards: number;
  };
}

export interface CreateFolderInput {
  userId: string;
  name: string;
  parentId?: string | null;
}

export interface ServiceResult<T> {
  success: boolean;
  data?: T;
  error?: string;
  details?: unknown; // Changed from any to unknown
  status?: number;
}

// --- GET Folders Logic ---
export async function getFoldersLogic(
  userId: string,
  prismaInstance: PrismaClient,
): Promise<ServiceResult<FolderBasicDetails[]>> {
  try {
    const folders = await prismaInstance.folder.findMany({
      where: { userId: userId },
      select: {
        id: true,
        name: true,
        parentId: true,
        updatedAt: true,
        _count: {
          select: {
            cards: true,
          },
        },
      },
      orderBy: {
        name: 'asc',
      },
    });
    return { success: true, data: folders, status: 200 };
  } catch (error) {
    console.error('[folderService] Failed to fetch folders:', error);
    return {
      success: false,
      error: 'Failed to retrieve folders.',
      status: 500,
    };
  }
}

// --- POST (Create) Folder Logic ---
export async function createFolderLogic(
  input: CreateFolderInput,
  prismaInstance: PrismaClient,
): Promise<
  ServiceResult<
    Prisma.FolderGetPayload<{
      select: { id: true; name: true; parentId: true; userId: true };
    }>
  >
> {
  const { userId, name, parentId } = input;
  try {
    // Validate parentId ownership if provided
    if (parentId) {
      const parentFolder = await prismaInstance.folder.findUnique({
        where: { id: parentId, userId: userId }, // Ensure user owns the parent
        select: { id: true },
      });
      if (!parentFolder) {
        return {
          success: false,
          error: 'Parent folder not found or not owned by user.',
          status: 400,
        };
      }
    }

    const newFolder = await prismaInstance.folder.create({
      data: {
        name,
        parentId,
        userId,
      },
      select: {
        // Select only necessary fields for the response
        id: true,
        name: true,
        parentId: true,
        userId: true, // Confirming ownership in response might be useful
      },
    });

    return { success: true, data: newFolder, status: 201 };
  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      if (error.code === 'P2002') {
        return {
          success: false,
          error: 'A folder with this name already exists at this level.',
          status: 409,
        };
      }
    }
    console.error('[folderService] Failed to create folder:', error);
    return {
      success: false,
      error: 'Failed to create folder.',
      details: (error as Error).message,
      status: 500,
    };
  }
}
