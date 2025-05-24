console.log(
  '[[FOLDERID ROUTE MODULE LOAD]] src/app/api/folders/[folderId]/route.ts loaded',
);

import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path as necessary
import prisma from '@/lib/prisma'; // Adjust path as necessary
import { z } from 'zod';
import { Prisma } from '@prisma/client';
// import { getCurrentUserId } from '@/lib/sessionUtils';
// import {
// findFolderForUpdateOrDelete, // This seems to be an internal detail of the service now
// } from '@/lib/services/folderService';

// Schema for validating the request body
const UpdateFolderSchema = z.object({
  name: z.string().trim().min(1, { message: 'Folder name cannot be empty' }),
});

// Schema for validating route parameters
const RouteParamsSchema = z.object({
  folderId: z.string().cuid({ message: 'Invalid folder ID format' }),
});

// Helper function for test authentication
async function getRouteHandlerUserId(
  request: NextRequest,
): Promise<string | null> {
  // console.log(`[[FOLDERID DEBUG]] APP_ENV: ${process.env.APP_ENV}`);
  if (process.env.APP_ENV === 'test') {
    const testUserId = request.headers.get('X-Test-User-Id');
    // console.log(`[[FOLDERID DEBUG]] Test mode. X-Test-User-Id header: "${testUserId}"`);
    if (testUserId && testUserId !== 'undefined' && testUserId !== 'null') {
      // console.log(`[[FOLDERID DEBUG]] Test override: Returning User ID: "${testUserId}".`);
      return testUserId;
    } else if (testUserId === 'null') {
      // console.log('[[FOLDERID DEBUG]] Test override: X-Test-User-Id is \'null\', returning null.');
      return null;
    } else {
      // console.log(`[[FOLDERID DEBUG]] Test override: X-Test-User-Id is "${testUserId}" (falsy or undefined string). Returning null from test path.`);
      return null;
    }
  }
  // console.log('[[FOLDERID DEBUG]] Not in test mode or fell through. Attempting real session.');
  const session = await getServerSession(authOptions);
  const finalUserId = session?.user?.id ?? null;
  // console.log(`[[FOLDERID DEBUG]] Real session result, returning User ID: "${finalUserId}".`);
  return finalUserId;
}

// --- PATCH Handler (Update/Rename Specific Folder) ---
export async function PATCH(
  req: NextRequest,
  context: { params: Promise<{ folderId: string }> },
) {
  // console.log('[[FOLDERID DEBUG]] PATCH handler entered');
  const userId = await getRouteHandlerUserId(req);
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const routeParams = await context.params;
  const paramsValidation = RouteParamsSchema.safeParse(routeParams);
  if (!paramsValidation.success) {
    return NextResponse.json(
      {
        error: 'Invalid folder ID format',
        details: paramsValidation.error.format(),
      },
      { status: 400 },
    );
  }
  const { folderId } = paramsValidation.data;

  let validatedBody;
  try {
    const body = await req.json();
    const validation = UpdateFolderSchema.safeParse(body);
    if (!validation.success) {
      return NextResponse.json(
        {
          error: 'Validation failed',
          details: validation.error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }
    validatedBody = validation.data;
  } catch {
    return NextResponse.json(
      { error: 'Invalid request body' },
      { status: 400 },
    );
  }

  try {
    const folderToUpdate = await prisma.folder.findUnique({
      where: { id: folderId, userId: userId },
    });

    if (!folderToUpdate) {
      return NextResponse.json(
        { error: 'Folder not found or not owned by user' },
        { status: 404 },
      );
    }

    const updatedFolder = await prisma.folder.update({
      where: {
        id: folderId,
      },
      data: {
        name: validatedBody.name,
      },
      select: {
        id: true,
        name: true,
        parentId: true,
        userId: true,
        updatedAt: true,
      }, // Match expected return shape
    });
    return NextResponse.json(updatedFolder, { status: 200 });
  } catch (error) {
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === 'P2002'
    ) {
      return NextResponse.json(
        { error: 'A folder with this name already exists at this level.' },
        { status: 409 },
      );
    }
    console.error('Failed to update folder:', error);
    return NextResponse.json(
      { error: 'Failed to update folder' },
      { status: 500 },
    );
  }
}

// --- DELETE Handler (Delete Specific Folder) ---
export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ folderId: string }> },
) {
  // console.log('[[FOLDERID DEBUG]] DELETE handler entered');
  const userId = await getRouteHandlerUserId(request);
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const resolvedParams = await context.params;
  const paramsValidation = RouteParamsSchema.safeParse(resolvedParams);
  if (!paramsValidation.success) {
    return NextResponse.json(
      {
        error: 'Invalid folder ID format',
        details: paramsValidation.error.format(),
      },
      { status: 400 },
    );
  }
  const { folderId } = paramsValidation.data;

  try {
    const folderToDelete = await prisma.folder.findUnique({
      where: { id: folderId, userId: userId },
      select: {
        parentId: true,
        _count: { select: { children: true, cards: true } },
      }, // Select for service logic
    });

    if (!folderToDelete) {
      return NextResponse.json(
        { error: 'Folder not found or not owned by user' },
        { status: 404 },
      );
    }

    // Transaction to move children and cards, then delete folder
    await prisma.$transaction(async (tx) => {
      await tx.knowledgeCard.updateMany({
        where: { folderId: folderId },
        data: { folderId: null }, // Or folderToDelete.parentId based on desired behavior
      });
      await tx.folder.updateMany({
        where: { parentId: folderId },
        data: { parentId: folderToDelete.parentId },
      });
      await tx.folder.delete({
        where: { id: folderId },
      });
    });

    return NextResponse.json(
      { message: 'Folder deleted successfully' },
      { status: 200 },
    );
  } catch (error) {
    console.error('Failed to delete folder:', error);
    return NextResponse.json(
      { error: 'Failed to delete folder' },
      { status: 500 },
    );
  }
}

export async function PUT(
  req: NextRequest,
  context: { params: Promise<{ folderId: string }> },
) {
  console.log('[[FOLDERID DEBUG]] PUT handler entered (now using PATCH logic)');
  const userId = await getRouteHandlerUserId(req);
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const routeParams = await context.params;
  const paramsValidation = RouteParamsSchema.safeParse(routeParams);
  if (!paramsValidation.success) {
    return NextResponse.json(
      {
        error: 'Invalid folder ID format',
        details: paramsValidation.error.format(),
      },
      { status: 400 },
    );
  }
  const { folderId } = paramsValidation.data;

  let validatedBody;
  try {
    const body = await req.json();
    const validation = UpdateFolderSchema.safeParse(body);
    if (!validation.success) {
      return NextResponse.json(
        {
          error: 'Validation failed',
          details: validation.error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }
    validatedBody = validation.data;
  } catch {
    return NextResponse.json(
      { error: 'Invalid request body' },
      { status: 400 },
    );
  }

  try {
    const folderToUpdate = await prisma.folder.findUnique({
      where: { id: folderId, userId: userId },
    });

    if (!folderToUpdate) {
      return NextResponse.json(
        { error: 'Folder not found or not owned by user' },
        { status: 404 },
      );
    }

    const updatedFolder = await prisma.folder.update({
      where: {
        id: folderId,
      },
      data: {
        name: validatedBody.name,
      },
      select: {
        id: true,
        name: true,
        parentId: true,
        userId: true,
        updatedAt: true,
      }, // Match expected return shape
    });
    return NextResponse.json(updatedFolder, { status: 200 });
  } catch (error) {
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === 'P2002'
    ) {
      return NextResponse.json(
        { error: 'A folder with this name already exists at this level.' },
        { status: 409 },
      );
    }
    console.error('Failed to update folder (PUT handler):', error);
    return NextResponse.json(
      { error: 'Failed to update folder' },
      { status: 500 },
    );
  }
}
