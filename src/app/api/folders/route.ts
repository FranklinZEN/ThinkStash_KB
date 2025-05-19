import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/lib/prisma';
import { getCurrentUserId } from '@/lib/sessionUtils';
import { z } from 'zod';
import {
  getFoldersLogic,
  createFolderLogic,
  CreateFolderInput,
} from '@/lib/services/folderService';

// Schema for validating the request body
const CreateFolderSchema = z.object({
  name: z.string().trim().min(1, { message: 'Folder name cannot be empty' }),
  parentId: z
    .string()
    .cuid({ message: 'Invalid parent folder ID' })
    .optional()
    .nullable(),
});

// --- GET Handler (List Folders) ---
export async function GET(_request: NextRequest) {
  console.time('[GET /api/folders] Total Handler');
  const userId = await getCurrentUserId();

  if (!userId) {
    console.timeEnd('[GET /api/folders] Total Handler');
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const result = await getFoldersLogic(userId, prisma);
  console.timeEnd('[GET /api/folders] Total Handler');

  if (result.success) {
    return NextResponse.json(result.data);
  } else {
    return NextResponse.json(
      { error: result.error },
      { status: result.status || 500 },
    );
  }
}

// --- POST Handler (Create Folder) ---
export async function POST(request: NextRequest) {
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
        {
          error: 'Validation failed',
          details: validation.error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }
    validatedData = validation.data;
  } catch {
    return NextResponse.json(
      { error: 'Invalid request body' },
      { status: 400 },
    );
  }

  const serviceInput: CreateFolderInput = {
    userId,
    name: validatedData.name,
    parentId: validatedData.parentId,
  };

  const result = await createFolderLogic(serviceInput, prisma);

  if (result.success) {
    return NextResponse.json(result.data, { status: result.status || 201 });
  } else {
    return NextResponse.json(
      { error: result.error, details: result.details },
      { status: result.status || 500 },
    );
  }
}
