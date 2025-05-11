import { NextResponse } from 'next/server';
import prisma from '@/lib/prisma';
import { getCurrentUserId } from '@/lib/sessionUtils';
import { z } from 'zod';
import { Prisma } from '@prisma/client';

// Schema for validating the request body
const CreateFolderSchema = z.object({
  name: z.string().min(1, { message: 'Folder name cannot be empty' }).trim(),
  parentId: z
    .string()
    .cuid({ message: 'Invalid parent folder ID' })
    .optional()
    .nullable(),
});

// --- GET Handler (List Folders) ---
export async function GET(_request: Request) {
  console.time('[GET /api/folders] Total Handler');
  console.time('[GET /api/folders] getCurrentUserId');
  const userId = await getCurrentUserId();
  console.timeEnd('[GET /api/folders] getCurrentUserId');

  if (!userId) {
    console.timeEnd('[GET /api/folders] Total Handler');
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    console.time('[GET /api/folders] Prisma findMany');
    const folders = await prisma.folder.findMany({
      where: { userId: userId },
      select: {
        id: true,
        name: true,
        parentId: true,
        updatedAt: true, // Include updatedAt for potential future sorting/display
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
    console.timeEnd('[GET /api/folders] Prisma findMany');
    console.timeEnd('[GET /api/folders] Total Handler');
    return NextResponse.json(folders);
  } catch (error) {
    console.error('Failed to fetch folders:', error);
    console.timeEnd('[GET /api/folders] Total Handler');
    // Consider more specific error handling if needed
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 },
    );
  }
}

// --- POST Handler (Create Folder) ---
export async function POST(request: Request) {
  const userId = await getCurrentUserId();

  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let validatedData;
  try {
    const body = await request.json();
    const validation = CreateFolderSchema.safeParse(body);

    if (!validation.success) {
      return NextResponse.json(
        { errors: validation.error.format() },
        { status: 400 },
      );
    }
    validatedData = validation.data;
  } catch /* _error */ {
    return NextResponse.json(
      { error: 'Invalid request body' },
      { status: 400 },
    );
  }

  try {
    // Validate parentId ownership if provided
    if (validatedData.parentId) {
      const parentFolder = await prisma.folder.findUnique({
        where: { id: validatedData.parentId, userId: userId },
        select: { id: true }, // Only select needed field
      });
      if (!parentFolder) {
        return NextResponse.json(
          { error: 'Parent folder not found or not owned by user' },
          { status: 400 },
        );
      }
    }

    // Create the folder
    const newFolder = await prisma.folder.create({
      data: {
        name: validatedData.name,
        parentId: validatedData.parentId,
        userId: userId,
      },
    });

    return NextResponse.json(newFolder, { status: 201 });
  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      // Handle unique constraint violation (duplicate name at the same level)
      if (error.code === 'P2002') {
        return NextResponse.json(
          { error: 'A folder with this name already exists at this level.' },
          { status: 409 }, // 409 Conflict
        );
      }
    }

    // Log unexpected errors
    console.error('Failed to create folder:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 },
    );
  }
}
