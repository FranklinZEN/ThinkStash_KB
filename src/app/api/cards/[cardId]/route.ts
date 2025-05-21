import { NextRequest, NextResponse } from 'next/server';
// import { getServerSession } from 'next-auth/next'; // Remove unused
// import { authOptions } from '@/lib/auth'; // Remove unused
import prisma from '@/lib/prisma'; // Ensure this is the default import
import { z } from 'zod';
// import { Prisma } from '@prisma/client'; // Remove unused
import { getCurrentUserId } from '@/lib/sessionUtils';
import {
  getCardLogic,
  updateCardLogic,
  deleteCardLogic,
  UpdateCardData, // Assuming this DTO is defined in cardService.ts
  // ServiceResult, // Not needed directly in route if just passing through
} from '@/lib/services/cardService';
import { CardContentSchema } from '@/lib/validators/editorValidators'; // Import CardContentSchema

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
  console.log(
    '[GET /api/cards/[cardId]] Context received by handler (raw promise):\n',
    context,
  );
  const resolvedParams = await context.params;
  console.log(
    '[GET /api/cards/[cardId]] Validating resolved params:',
    JSON.stringify(resolvedParams),
  );
  const paramsValidation = CardIdParamsSchema.safeParse(resolvedParams);

  if (!paramsValidation.success) {
    console.error(
      '[GET /api/cards/[cardId]] Params validation failed:',
      paramsValidation.error.format(),
    );
    return NextResponse.json(
      {
        error: 'Invalid card ID format',
        details: paramsValidation.error.format(),
      },
      { status: 400 },
    );
  }
  const { cardId } = paramsValidation.data;
  console.log(
    '[GET /api/cards/[cardId]] Params validation success, cardId:',
    cardId,
  );

  const userId = await getCurrentUserId();
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const result = await getCardLogic(cardId, userId, prisma);

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
  console.log(
    '[PUT /api/cards/[cardId]] Context received by handler (raw promise):\n',
    context,
  );
  const resolvedParams = await context.params;
  console.log(
    '[PUT /api/cards/[cardId]] Validating resolved params:',
    JSON.stringify(resolvedParams),
  );
  const paramsValidation = CardIdParamsSchema.safeParse(resolvedParams);

  if (!paramsValidation.success) {
    console.error(
      '[PUT /api/cards/[cardId]] Params validation failed:',
      paramsValidation.error.format(),
    );
    return NextResponse.json(
      {
        error: 'Invalid card ID format',
        details: paramsValidation.error.format(),
      },
      { status: 400 },
    );
  }
  const { cardId } = paramsValidation.data;
  console.log(
    '[PUT /api/cards/[cardId]] Params validation success, cardId:',
    cardId,
  );

  const userId = await getCurrentUserId();
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

  const result = await updateCardLogic(cardId, userId, validatedBody, prisma);

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
  console.log(
    '[DELETE /api/cards/[cardId]] Context received by handler (raw promise):\n',
    context,
  );
  const resolvedParams = await context.params;
  console.log(
    '[DELETE /api/cards/[cardId]] Validating resolved params:',
    JSON.stringify(resolvedParams),
  );
  const paramsValidation = CardIdParamsSchema.safeParse(resolvedParams);

  if (!paramsValidation.success) {
    console.error(
      '[DELETE /api/cards/[cardId]] Params validation failed:',
      paramsValidation.error.format(),
    );
    return NextResponse.json(
      {
        error: 'Invalid card ID format',
        details: paramsValidation.error.format(),
      },
      { status: 400 },
    );
  }
  const { cardId } = paramsValidation.data;
  console.log(
    '[DELETE /api/cards/[cardId]] Params validation success, cardId:',
    cardId,
  );

  const userId = await getCurrentUserId();
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Note: The service deleteCardLogic does not currently handle GCS file cleanup.
  // This should be added either to the service or orchestrated here if ImageRecords need to be fetched first.
  // For now, just calling the service as is.
  const result = await deleteCardLogic(cardId, userId, prisma);

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
