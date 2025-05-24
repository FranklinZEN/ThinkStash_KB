// console.log('[[CARDS ROUTE MODULE LOAD]] src/app/api/cards/[cardId]/route.ts loaded');

import { NextRequest, NextResponse } from 'next/server';
// import { getServerSession } from 'next-auth/next'; // Remove unused
// import { authOptions } from '@/lib/auth'; // Remove unused
import { z } from 'zod';
// import { Prisma } from '@prisma/client'; // Remove unused
import { getServerSession } from 'next-auth/next'; // Keep for actual auth
import { authOptions } from '@/lib/auth'; // Keep for actual auth
import {
  getCardLogic,
  updateCardLogic,
  deleteCardLogic,
  UpdateCardData, // Assuming this DTO is defined in cardService.ts
  // ServiceResult, // Not needed directly in route if just passing through
} from '@/lib/services/cardService';
import { CardContentSchema } from '@/lib/validators/editorValidators'; // Import CardContentSchema

// Helper function for test authentication
async function getRouteHandlerUserId(
  request: NextRequest,
): Promise<string | null> {
  // console.log(`[getRouteHandlerUserId] APP_ENV: ${process.env.APP_ENV}`); // Keep for now if helpful
  if (process.env.APP_ENV === 'test') {
    const testUserId = request.headers.get('X-Test-User-Id');
    // console.log(`[getRouteHandlerUserId] Test mode. X-Test-User-Id header: ${testUserId}`);
    if (testUserId) {
      if (testUserId === 'null') return null;
      return testUserId;
    }
  }
  const session = await getServerSession(authOptions);
  return session?.user?.id ?? null;
}

// interface RouteParams { // This interface will be removed
//   params: Promise<{ cardId: string }>;
// }

// Schema for validating route parameters (params object directly)
const CardIdParamsSchema = z.object({
  cardId: z.string().cuid({ message: 'Invalid card ID format' }),
});

// Schema for validating the update request body (PATCH/PUT)
// Allow partial updates: title, content, or folderId
const UpdateCardSchema = z
  .object({
    title: z
      .string()
      .min(1, { message: 'Title cannot be empty' })
      .trim()
      .optional(),
    content: CardContentSchema.optional(), // Use CardContentSchema for content validation
    folderId: z
      .string()
      .cuid({ message: 'Invalid folder ID format.' })
      .optional()
      .nullable(), // Reverted to CUID check for folderId
    tags: z.array(z.string().trim().min(1)).optional(), // Ensure tags are non-empty strings if array is provided
  })
  .partial()
  .refine((data) => Object.keys(data).length > 0, {
    message:
      'At least one field (title, content, folderId, tags) must be provided for update',
  });

// --- GET Handler (Get Specific Card) ---
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ cardId: string }> },
) {
  // console.log('[[CARDS ROUTE DEBUG]] GET /api/cards/[cardId] HANDLER ENTERED');
  const resolvedParams = await context.params;
  const paramsValidation = CardIdParamsSchema.safeParse(resolvedParams);

  if (!paramsValidation.success) {
    // console.error('[GET /api/cards/[cardId]] Params validation failed:', paramsValidation.error.format()); // Reduced logging
    return NextResponse.json(
      {
        error: 'Invalid card ID format',
        details: paramsValidation.error.format(),
      },
      { status: 400 },
    );
  }
  const { cardId } = paramsValidation.data;
  const userId = await getRouteHandlerUserId(request);
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  const result = await getCardLogic(cardId, userId);
  if (result.success) {
    return NextResponse.json(result.data, { status: result.status });
  } else {
    return NextResponse.json(
      { error: result.error, details: result.details },
      { status: result.status || 500 },
    );
  }
}

// --- PUT Handler (Update Specific Card) ---
export async function PUT(
  req: NextRequest,
  context: { params: Promise<{ cardId: string }> },
) {
  const resolvedParams = await context.params;
  const paramsValidation = CardIdParamsSchema.safeParse(resolvedParams);

  if (!paramsValidation.success) {
    // console.error('[PUT /api/cards/[cardId]] Params validation failed:', paramsValidation.error.format()); // Reduced logging
    return NextResponse.json(
      {
        error: 'Invalid card ID format',
        details: paramsValidation.error.format(),
      },
      { status: 400 },
    );
  }
  const { cardId } = paramsValidation.data;
  const userId = await getRouteHandlerUserId(req);
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  let validatedBody: UpdateCardData;
  try {
    const body = await req.json();
    const validationResult = UpdateCardSchema.safeParse(body);
    if (!validationResult.success) {
      return NextResponse.json(
        {
          error: 'Validation failed',
          details: validationResult.error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }
    validatedBody = validationResult.data as UpdateCardData;
  } catch {
    return NextResponse.json(
      { error: 'Invalid request body' },
      { status: 400 },
    );
  }
  const result = await updateCardLogic(cardId, userId, validatedBody);
  if (result.success) {
    return NextResponse.json(result.data, { status: result.status });
  } else {
    return NextResponse.json(
      { error: result.error, details: result.details },
      { status: result.status || 500 },
    );
  }
}

// --- DELETE Handler (Delete Specific Card) ---
export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ cardId: string }> },
) {
  const resolvedParams = await context.params;
  const paramsValidation = CardIdParamsSchema.safeParse(resolvedParams);

  if (!paramsValidation.success) {
    // console.error('[DELETE /api/cards/[cardId]] Params validation failed:', paramsValidation.error.format()); // Reduced logging
    return NextResponse.json(
      {
        error: 'Invalid card ID format',
        details: paramsValidation.error.format(),
      },
      { status: 400 },
    );
  }
  const { cardId } = paramsValidation.data;
  const userId = await getRouteHandlerUserId(request);
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  const result = await deleteCardLogic(cardId, userId);
  if (result.success) {
    return NextResponse.json(
      { message: 'Card deleted successfully' },
      { status: result.status },
    );
  } else {
    return NextResponse.json(
      { error: result.error, details: result.details },
      { status: result.status || 500 },
    );
  }
}
