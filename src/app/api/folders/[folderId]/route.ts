import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path as necessary
import { prisma } from '@/lib/prisma'; // Adjust path as necessary
import { z } from 'zod';
import { Prisma } from '@prisma/client';
import { getCurrentUserId } from '@/lib/sessionUtils';

interface RouteParams {
  params: {
    folderId: string;
  };
}

// Schema for validating the request body
const UpdateFolderSchema = z.object({
  name: z.string().min(1, { message: 'Folder name cannot be empty' }).trim(),
});

// Schema for validating route parameters
const RouteParamsSchema = z.object({
  folderId: z.string().cuid({ message: 'Invalid folder ID format' }),
});

// Helper function to verify folder ownership
async function verifyFolderOwnership(userId: string, folderId: string) {
  const folder = await prisma.folder.findUnique({
    where: { id: folderId },
  });
  if (!folder) {
    return { error: NextResponse.json({ message: 'Folder not found' }, { status: 404 }), folder: null };
  }
  if (folder.userId !== userId) {
    return { error: NextResponse.json({ message: 'Forbidden' }, { status: 403 }), folder: null };
  }
  return { error: null, folder: folder };
}

// --- PATCH Handler (Update/Rename Specific Folder) ---
export async function PATCH(req: NextRequest, { params }: RouteParams) {
  const session = await getServerSession(authOptions);
  const { folderId } = params;

  if (!session || !session.user?.id) {
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  const userId = session.user.id;

  try {
    // Verify ownership first
    const { error: ownershipError } = await verifyFolderOwnership(userId, folderId);
    if (ownershipError) return ownershipError;

    const body = await req.json();
    const { name } = body;

    // Validate new name
    if (!name || typeof name !== 'string' || name.trim().length === 0) {
      return NextResponse.json({ message: 'New folder name is required and must be a non-empty string' }, { status: 400 });
    }
    const trimmedName = name.trim();

    // Check if another folder with the same name already exists for this user (excluding the current one)
    const existingFolder = await prisma.folder.findFirst({
      where: {
        userId: userId,
        name: trimmedName,
        id: { not: folderId }, // Exclude the folder being renamed
      },
    });

    if (existingFolder) {
      return NextResponse.json({ message: `Another folder named "${trimmedName}" already exists` }, { status: 409 });
    }

    // Update the folder name
    const updatedFolder = await prisma.folder.update({
      where: { id: folderId },
      data: { name: trimmedName },
    });

    return NextResponse.json(updatedFolder, { status: 200 });

  } catch (err) {
    console.error('Update Folder [id] Error:', err);
    return NextResponse.json({ message: 'Internal Server Error' }, { status: 500 });
  }
}

// --- DELETE Handler (Delete Specific Folder - updated with content handling) ---
export async function DELETE(request: Request, { params }: { params: { folderId: string } }) {
  // Await params as recommended by Next.js error message
  // It seems params can sometimes be promise-like in certain conditions
  const resolvedParams = await params; 
  console.log("[DELETE /api/folders/[folderId]] Resolved params:", resolvedParams);

  // Validate route parameters using resolvedParams
  const paramsValidation = RouteParamsSchema.safeParse(resolvedParams);
  if (!paramsValidation.success) {
    console.error("[DELETE /api/folders/[folderId]] Zod validation failed:", paramsValidation.error.format());
    return NextResponse.json({ errors: paramsValidation.error.format() }, { status: 400 });
  }
  const { folderId } = paramsValidation.data;
  console.log(`[DELETE /api/folders/[folderId]] Validated folderId: ${folderId}`);

  // Check authentication
  const userId = await getCurrentUserId();
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    // Find the folder to get its parentId and verify ownership
    const folderToDelete = await prisma.folder.findUnique({
      where: {
        id: folderId,
        userId: userId, // Ensure user owns the folder
      },
      select: { parentId: true } // Need parentId for promoting children
    });

    // Handle folder not found or not owned
    if (!folderToDelete) {
      return NextResponse.json({ error: 'Folder not found or not owned by user' }, { status: 404 });
    }

    // Perform updates and delete within a transaction
    await prisma.$transaction(async (tx) => {
      // 1. Uncategorize cards within the folder
      await tx.knowledgeCard.updateMany({
        where: { folderId: folderId },
        data: { folderId: null },
      });

      // 2. Promote direct subfolders
      await tx.folder.updateMany({
        where: { parentId: folderId },
        data: { parentId: folderToDelete.parentId }, // Move children to grandparent
      });

      // 3. Delete the folder itself
      await tx.folder.delete({
        where: { id: folderId },
      });
    });

    // Return success response
    return NextResponse.json({ message: 'Folder deleted successfully' }, { status: 200 });

  } catch (error) {
    // Log unexpected errors
    console.error('Failed to delete folder:', error);
    // Consider more specific error handling if needed
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}

export async function PUT(request: Request, { params }: { params: { folderId: string } }) {
  // Validate route parameters
  const paramsValidation = RouteParamsSchema.safeParse(params);
  if (!paramsValidation.success) {
    return NextResponse.json({ errors: paramsValidation.error.format() }, { status: 400 });
  }
  const { folderId } = paramsValidation.data;

  // Check authentication
  const userId = await getCurrentUserId();
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Validate request body
  let validatedData;
  try {
    const body = await request.json();
    const validation = UpdateFolderSchema.safeParse(body);
    if (!validation.success) {
      return NextResponse.json({ errors: validation.error.format() }, { status: 400 });
    }
    validatedData = validation.data;
  } catch (error) {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }

  try {
    // Verify user owns the folder they are trying to update
    const existingFolder = await prisma.folder.findUnique({
      where: { id: folderId, userId: userId },
      select: { id: true }, // Only select necessary field
    });

    if (!existingFolder) {
      return NextResponse.json({ error: 'Folder not found or not owned by user' }, { status: 404 });
    }

    // Attempt to update the folder
    const updatedFolder = await prisma.folder.update({
      where: {
        id: folderId,
        // No need to re-check userId here, checked above
      },
      data: {
        name: validatedData.name,
      },
    });

    return NextResponse.json(updatedFolder);

  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      // Handle unique constraint violation (duplicate name at the same level)
      if (error.code === 'P2002') {
        return NextResponse.json(
          { error: 'A folder with this name already exists at this level.' },
          { status: 409 } // 409 Conflict
        );
      }
    }

    // Log unexpected errors
    console.error('Failed to update folder:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
} 