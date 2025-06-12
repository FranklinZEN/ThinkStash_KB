// console.log('[CARDS ROUTE MODULE LOAD] src/app/api/cards/[cardId]/route.ts loaded');

import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth';
import {
  getCardLogic,
  updateCardLogic,
  deleteCardLogic,
  UpdateCardData,
} from '@/lib/services/cardService'; // Restored
import { CardContentSchema } from '@/lib/validators/editorValidators'; // Restored
import { z } from 'zod'; // Added for Zod
// import type { UpdateCardRequest, KnowledgeCardResponse } from '@/types/api/ai-service'; // This seems like a leftover from AI services, not directly used by card CRUD. Keeping commented.

// Removed CardRouteContext interface
// interface CardRouteContext {
//   params: {
//     cardId: string;
//   };
// }

const CardIdParamsSchema = z.object({
  // Restored
  cardId: z.string().cuid({ message: 'Invalid card ID format' }),
});

const UpdateCardBodySchema = z // Restored & Renamed for clarity
  .object({
    title: z
      .string()
      .min(1, { message: 'Title cannot be empty' })
      .trim()
      .optional(),
    content: CardContentSchema.optional(),
    folderId: z
      .string()
      .cuid({ message: 'Invalid folder ID format.' })
      .optional()
      .nullable(),
    tags: z.array(z.string().trim().min(1)).optional(),
    // isStarred, isPublic, isArchived could be added here if they are updatable via this route
  })
  .partial()
  .refine((data) => Object.keys(data).length > 0, {
    message:
      'At least one field (title, content, folderId, tags) must be provided for update',
  });

// interface RouteContext { // Not explicitly needed as Next.js infers it with { params }
//   params: {
//     cardId: string;
//   };
// }

// GET /api/cards/[cardId] (Get a single card)
export async function GET(
  req: NextRequest,
  context: { params: Promise<{ cardId: string }> },
) {
  try {
    const routeParams = await context.params;

    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userId = session.user.id;

    const paramsValidation = CardIdParamsSchema.safeParse(routeParams);
    if (!paramsValidation.success) {
      // console.error("API GET /api/cards/[cardId] - Zod schema validation failed:", JSON.stringify(paramsValidation.error.flatten(), null, 2)); // Keep this if desired, or remove
      return NextResponse.json(
        {
          error: 'Invalid card ID format',
          details: paramsValidation.error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }
    const { cardId } = paramsValidation.data;

    const result = await getCardLogic(cardId, userId);

    if (!result.success || !result.data) {
      return NextResponse.json(
        { error: result.error || 'Card not found or access denied' },
        { status: result.status || 404 },
      );
    }
    // On success, return only the card data.
    return NextResponse.json(result.data);
  } catch (error) {
    console.error(`Error in /cards/[cardId] (GET):`, error);
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    // Check for ZodError for more specific client messages if needed
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Validation failed', details: error.flatten().fieldErrors },
        { status: 400 },
      );
    }
    return NextResponse.json(
      { error: 'Failed to fetch card.', details: errorMessage },
      { status: 500 },
    );
  }
}

// PUT /api/cards/[cardId] (Update a card)
export async function PUT(
  req: NextRequest,
  context: { params: Promise<{ cardId: string }> },
) {
  try {
    const routeParams = await context.params; // Await here

    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userId = session.user.id;

    const paramsValidation = CardIdParamsSchema.safeParse(routeParams); // Validate awaited params
    if (!paramsValidation.success) {
      return NextResponse.json(
        {
          error: 'Invalid card ID format',
          details: paramsValidation.error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }
    const { cardId } = paramsValidation.data;

    let rawBody;
    try {
      rawBody = await req.json();
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
    } catch (_) {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }

    const bodyValidation = UpdateCardBodySchema.safeParse(rawBody);
    if (!bodyValidation.success) {
      return NextResponse.json(
        {
          error: 'Validation failed',
          details: bodyValidation.error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }
    const validatedBody = bodyValidation.data as UpdateCardData;

    // console.log(`API /cards/${cardId} (PUT) called by user ${userId} with body:`, validatedBody); // Debug logging

    const result = await updateCardLogic(cardId, userId, validatedBody);

    if (!result.success || !result.data) {
      return NextResponse.json(
        { error: result.error || 'Failed to update card or card not found' },
        {
          status:
            result.status || (result.error?.includes('not found') ? 404 : 500),
        },
      );
    }
    // On success, return only the updated card data.
    return NextResponse.json(result.data);
  } catch (error) {
    console.error(`Error in /cards/[cardId] (PUT):`, error);
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    if (error instanceof z.ZodError) {
      // Catch Zod errors from body parsing if not caught earlier or service re-throws
      return NextResponse.json(
        { error: 'Validation failed', details: error.flatten().fieldErrors },
        { status: 400 },
      );
    }
    return NextResponse.json(
      { error: 'Failed to update card.', details: errorMessage },
      { status: 500 },
    );
  }
}

// DELETE /api/cards/[cardId] (Delete a card)
export async function DELETE(
  req: NextRequest,
  context: { params: Promise<{ cardId: string }> },
) {
  try {
    const routeParams = await context.params; // Await here

    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userId = session.user.id;

    const paramsValidation = CardIdParamsSchema.safeParse(routeParams); // Validate awaited params
    if (!paramsValidation.success) {
      return NextResponse.json(
        {
          error: 'Invalid card ID format',
          details: paramsValidation.error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }
    const { cardId } = paramsValidation.data;

    // console.log(`API /cards/${cardId} (DELETE) called by user ${userId}`); // Debug logging

    const result = await deleteCardLogic(cardId, userId);

    if (!result.success) {
      return NextResponse.json(
        {
          error: result.error || 'Failed to delete card',
          details: result.details,
        },
        { status: result.status || 404 },
      );
    }
    // If deleteCardLogic returns a success payload (even if data is minimal/just an ID or null)
    return NextResponse.json(
      { message: 'Card deleted successfully' },
      { status: 200 },
    );
  } catch (error) {
    console.error(`Error in /cards/[cardId] (DELETE):`, error);
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Validation failed', details: error.flatten().fieldErrors },
        { status: 400 },
      );
    }
    return NextResponse.json(
      { error: 'Failed to delete card.', details: errorMessage },
      { status: 500 },
    );
  }
}
