import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path as necessary
import prisma from '@/lib/prisma'; // Ensure this is the default import
import { z } from 'zod';
import { Prisma } from '@prisma/client';
import { getCurrentUserId } from '@/lib/sessionUtils';

// interface RouteParams { // This interface will be removed
//   params: Promise<{ cardId: string }>;
// }

// Schema for validating route parameters
const RouteContextSchema = z.object({
  params: z.object({
    cardId: z.string().cuid({ message: 'Invalid card ID format' }),
  }),
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
    content: z
      .array(z.any())
      .min(1, { message: 'Content cannot be empty' })
      .optional(), // Basic check for non-empty array
    folderId: z
      .string()
      .cuid({ message: 'Invalid folder ID format' })
      .optional()
      .nullable(), // Allow setting to null
    tags: z.array(z.string().trim()).optional(), // Added tags to schema, expect array of strings
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
  console.time('[GET /api/cards/[cardId]] Total Handler');
  console.time('[GET /api/cards/[cardId]] Session Check');
  const session = await getServerSession(authOptions);
  console.timeEnd('[GET /api/cards/[cardId]] Session Check');

  if (!session || !session.user?.id) {
    console.timeEnd('[GET /api/cards/[cardId]] Total Handler'); // End total timer early on auth failure
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const userId = session.user.id;

  console.time('[GET /api/cards/[cardId]] Resolve Params');
  const resolvedParams = await context.params;
  console.timeEnd('[GET /api/cards/[cardId]] Resolve Params');

  try {
    const cardId = resolvedParams.cardId;
    if (!cardId) {
      console.timeEnd('[GET /api/cards/[cardId]] Total Handler'); // End total timer early
      return NextResponse.json(
        { error: 'Card ID is required' },
        { status: 400 },
      );
    }

    console.time('[GET /api/cards/[cardId]] Prisma findUnique');
    const card = await prisma.knowledgeCard.findUnique({
      where: {
        id: cardId,
        userId: userId, // Ensure user owns the card
      },
      include: {
        folder: true, // Include full folder data if needed
        tags: true, // Include full tag data if needed
      },
    });
    console.timeEnd('[GET /api/cards/[cardId]] Prisma findUnique');

    if (!card) {
      console.timeEnd('[GET /api/cards/[cardId]] Total Handler'); // End total timer early
      return NextResponse.json(
        { error: 'Card not found or access denied' },
        { status: 404 },
      );
    }
    console.timeEnd('[GET /api/cards/[cardId]] Total Handler');
    return NextResponse.json(card);
  } catch (error) {
    console.error('Error fetching card:', error);
    console.timeEnd('[GET /api/cards/[cardId]] Total Handler'); // End total timer on error
    return NextResponse.json(
      { error: 'Failed to fetch card' },
      { status: 500 },
    );
  }
}

// --- PUT Handler (Update Specific Card) ---
export async function PUT(
  req: NextRequest,
  context: { params: Promise<{ cardId: string }> },
) {
  console.log('[PUT /api/cards/] Handler Entered');

  console.log('[PUT /api/cards/] Raw context received:', context);

  let resolvedParams;
  try {
    resolvedParams = await context.params;
    console.log('[PUT /api/cards/] Resolved params:', resolvedParams);
  } catch (err) {
    console.error('Error awaiting context.params:', err);
    return NextResponse.json(
      { error: 'Failed to resolve route parameters' },
      { status: 500 },
    );
  }

  const contextValidation = RouteContextSchema.safeParse({
    params: resolvedParams,
  });
  if (!contextValidation.success) {
    console.error(
      'Route context validation failed (after await):',
      contextValidation.error.format(),
    );
    return NextResponse.json(
      { errors: contextValidation.error.format() },
      { status: 400 },
    );
  }
  const { cardId } = contextValidation.data.params;

  const userId = await getCurrentUserId();
  console.log(`[PUT /api/cards/${cardId}] Authenticated userId:`, userId);
  if (!userId) {
    console.error('User ID not found, returning 401');
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let validatedData;
  let body;
  try {
    body = await req.json();
    console.log('[PUT /api/cards/] Request body parsed:', body);

    const validation = UpdateCardSchema.safeParse(body);
    if (!validation.success) {
      console.error(
        'Request body validation failed:',
        validation.error.format(),
      );
      return NextResponse.json(
        { errors: validation.error.format() },
        { status: 400 },
      );
    }
    console.log('[PUT /api/cards/] Request body validated successfully.');
    validatedData = validation.data;
  } catch (error) {
    console.error('Error parsing request body:', error);
    return NextResponse.json(
      { error: 'Invalid request body' },
      { status: 400 },
    );
  }

  try {
    const existingCard = await prisma.knowledgeCard.findUnique({
      where: { id: cardId, userId: userId },
      select: { id: true },
    });

    if (!existingCard) {
      return NextResponse.json(
        { error: 'Card not found or not owned by user' },
        { status: 404 },
      );
    }

    if (
      validatedData.folderId !== undefined &&
      validatedData.folderId !== null
    ) {
      console.log(
        `Checking folder ownership: folderId=${validatedData.folderId}, userId=${userId}`,
      );

      const targetFolder = await prisma.folder.findUnique({
        where: { id: validatedData.folderId, userId: userId },
        select: { id: true },
      });
      if (!targetFolder) {
        return NextResponse.json(
          { error: 'Target folder not found or not owned by user' },
          { status: 400 },
        );
      }
    }

    const updateData: Prisma.KnowledgeCardUpdateInput = {};
    if (validatedData.title !== undefined)
      updateData.title = validatedData.title;
    if (validatedData.content !== undefined)
      updateData.content = validatedData.content;
    // if (validatedData.folderId !== undefined) updateData.folderId = validatedData.folderId;

    // Handle folderId update using relation syntax
    if (validatedData.folderId !== undefined) {
      // If folderId was part of the validated request data
      if (validatedData.folderId === null) {
        // To set folderId to null, disconnect the relation
        updateData.folder = {
          disconnect: true,
        };
      } else {
        // To set folderId to a new ID, connect the relation
        updateData.folder = {
          connect: { id: validatedData.folderId },
        };
      }
    }

    // Handle tags update
    if (validatedData.tags !== undefined) {
      // If tags array is provided (even if empty)
      const uniqueTrimmedTags = validatedData.tags
        .map((tag) => tag.trim())
        .filter((tag) => tag.length > 0);
      updateData.tags = {
        set: [], // Disconnect all existing tags first
        connectOrCreate: uniqueTrimmedTags.map((tagName: string) => ({
          where: { name: tagName },
          create: { name: tagName },
        })),
      };
    }

    const updatedCard = await prisma.knowledgeCard.update({
      where: {
        id: cardId,
      },
      data: updateData,
      include: { tags: true, folder: true },
    });

    return NextResponse.json(updatedCard);
  } catch (error) {
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      if (error.code === 'P2003') {
        return NextResponse.json(
          { error: 'Invalid related data (e.g., folder ID)' },
          { status: 400 },
        );
      }
    }

    console.error('Failed to update card:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 },
    );
  }
}

// --- DELETE Handler (Delete Specific Card) ---
export async function DELETE(
  req: NextRequest,
  context: { params: Promise<{ cardId: string }> },
) {
  let resolvedParams;
  try {
    resolvedParams = await context.params;
  } catch (err) {
    console.error(
      '[DELETE /api/cards/[cardId]] Error awaiting route parameters:',
      err,
    );
    return NextResponse.json(
      { error: 'Failed to resolve route parameters' },
      { status: 500 },
    );
  }

  console.log(
    `[DELETE /api/cards/[cardId]] Received cardId (from resolvedParams): ${resolvedParams?.cardId}`,
  );

  const paramsValidation = RouteContextSchema.safeParse({
    params: resolvedParams,
  });
  if (!paramsValidation.success) {
    console.error(
      '[DELETE /api/cards/[cardId]] Route parameter validation failed:',
      paramsValidation.error.format(),
    );
    return NextResponse.json(
      {
        error: 'Invalid card ID format in URL',
        details: paramsValidation.error.format(),
      },
      { status: 400 },
    );
  }
  const { cardId } = paramsValidation.data.params;
  console.log(`[DELETE /api/cards/[cardId]] Validated cardId: ${cardId}`);

  const userId = await getCurrentUserId();
  if (!userId) {
    console.error(
      '[DELETE /api/cards/[cardId]] Unauthorized: No userId found from session.',
    );
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  console.log(`[DELETE /api/cards/[cardId]] Authenticated userId: ${userId}`);

  try {
    console.time(
      '[DELETE /api/cards/[cardId]] Prisma findUnique (ownership check)',
    );
    const existingCard = await prisma.knowledgeCard.findUnique({
      where: { id: cardId, userId: userId },
      select: { id: true },
    });
    console.timeEnd(
      '[DELETE /api/cards/[cardId]] Prisma findUnique (ownership check)',
    );

    if (!existingCard) {
      console.warn(
        `[DELETE /api/cards/[cardId]] Card not found or user does not own it. cardId: ${cardId}, userId: ${userId}`,
      );
      return NextResponse.json(
        { error: 'Card not found or not owned by user' },
        { status: 404 },
      );
    }
    console.log(
      `[DELETE /api/cards/[cardId]] Ownership verified for cardId: ${cardId}`,
    );

    console.time('[DELETE /api/cards/[cardId]] Prisma delete');
    await prisma.knowledgeCard.delete({
      where: { id: cardId },
    });
    console.timeEnd('[DELETE /api/cards/[cardId]] Prisma delete');
    console.log(
      `[DELETE /api/cards/[cardId]] Card deleted successfully: ${cardId}`,
    );

    return NextResponse.json(
      { message: 'Card deleted successfully' },
      { status: 200 },
    );
  } catch (err) {
    console.error(
      `[DELETE /api/cards/[cardId]] Error during deletion process for cardId: ${cardId}:`,
      err,
    );
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 },
    );
  }
}
