import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { z } from 'zod';
import {
  getFoldersLogic,
  createFolderLogic,
  CreateFolderInput,
} from '@/lib/services/folderService';

export const runtime = 'nodejs'; // Force Node.js runtime

// console.log(`[/api/folders/route.ts MODULE LOAD] Current NODE_ENV: ${process.env.NODE_ENV}`);

// Schema for validating the request body
const CreateFolderSchema = z.object({
  name: z.string().trim().min(1, { message: 'Folder name cannot be empty' }),
  parentId: z
    .string()
    .cuid({ message: 'Invalid parent folder ID' })
    .optional()
    .nullable(),
});

async function getEffectiveUserId(req: NextRequest): Promise<string | null> {
  // console.log('[/api/folders] getEffectiveUserId called.');
  if (process.env.APP_ENV === 'test') {
    // console.log('[/api/folders] In test mode (APP_ENV=test).');
    const testUserId = req.headers.get('X-Test-User-Id');
    // console.log(`[/api/folders] X-Test-User-Id header raw value: "${testUserId}" (type: ${typeof testUserId})`);

    if (testUserId && testUserId !== 'undefined') {
      // console.log(`[/api/folders] testUserId is considered present: "${testUserId}"`);
      if (testUserId === 'null') {
        // console.log('[/api/folders] Test override: Returning NULL for user (unauthenticated).');
        return null;
      }
      // console.log(`[/api/folders] Test override: Returning User ID: "${testUserId}".`);
      return testUserId;
    }
    // If in test mode and X-Test-User-Id is not present or is 'undefined',
    // behavior for tests would be unauthenticated. Do not fall through to real session.
    // console.log('[/api/folders] testUserId "${testUserId}" is NOT present or is 'undefined' IN TEST MODE. Returning null.');
    return null;
  }

  // console.log('[/api/folders] Not in test override path. Attempting real session.');
  const session = await getServerSession(authOptions);
  if (session && session.user && session.user.id) {
    // console.log(`[/api/folders] Real session found for user: ${session.user.id}`);
    return session.user.id;
  }
  // console.log('[/api/folders] No real session found or no user ID in session.');
  return null;
}

export async function GET(request: NextRequest) {
  // console.log('[[FOLDER ROUTE DEBUG]] GET /api/folders HANDLER ENTERED');
  // console.time('[GET /api/folders] Total Handler');
  const userId = await getEffectiveUserId(request);

  if (!userId) {
    // console.timeEnd('[GET /api/folders] Total Handler');
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const result = await getFoldersLogic(userId);
  // console.timeEnd('[GET /api/folders] Total Handler');

  if (result.success) {
    return NextResponse.json(result.data);
  } else {
    return NextResponse.json(
      { error: result.error },
      { status: result.status || 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  const userId = await getEffectiveUserId(request);

  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let validatedData;
  // let bodyForLogging: any = '[Not Parsed Yet]'; // Keep for debugging if needed, but remove from default
  try {
    const body = await request.json();
    // bodyForLogging = body;
    // console.log('[/api/folders POST] Parsed request body:', bodyForLogging);

    const validation = CreateFolderSchema.safeParse(body);

    if (!validation.success) {
      const validationErrors = validation.error.flatten().fieldErrors;
      // console.error('[/api/folders POST] Zod validation failed. Body:', body, 'Errors:', validationErrors);
      return NextResponse.json(
        {
          error: 'Validation failed',
          details: validationErrors,
        },
        { status: 400 },
      );
    }
    validatedData = validation.data;
    // console.log('[/api/folders POST] Zod validation successful. Validated data:', validatedData);
  } catch (e: unknown) {
    const errorTimestamp = new Date().toISOString();
    const message = e instanceof Error ? e.message : String(e);
    console.error(
      '[/api/folders POST] Failed to parse body or validation error:',
      message,
    );
    return NextResponse.json(
      { error: 'Invalid request body', message, caughtAt: errorTimestamp },
      { status: 400 },
    );
  }

  const serviceInput: CreateFolderInput = {
    userId,
    name: validatedData.name,
    parentId: validatedData.parentId,
  };

  const result = await createFolderLogic(serviceInput);

  if (result.success) {
    return NextResponse.json(result.data, { status: result.status || 201 });
  } else {
    // Log service layer errors for visibility in production if they are not caught and logged deeper
    // console.error(`[/api/folders POST] Service logic error: ${result.error}`, result.details);
    return NextResponse.json(
      { error: result.error, details: result.details }, // Ensure details are passed if present
      { status: result.status || 500 },
    );
  }
}
