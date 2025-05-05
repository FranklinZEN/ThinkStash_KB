import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path as necessary
import prisma from '@/lib/prisma'; // Ensure this is the default import
import { z } from 'zod';
import { Prisma } from '@prisma/client';
import { getCurrentUserId } from '@/lib/sessionUtils';

interface RouteParams {
  params: {
    cardId: string;
  };
}

// Schema for validating route parameters
const RouteContextSchema = z.object({
  params: z.object({
    cardId: z.string().cuid({ message: 'Invalid card ID format' }),
  }),
});

// Schema for validating the update request body (PATCH/PUT)
// Allow partial updates: title, content, or folderId
const UpdateCardSchema = z.object({
  title: z.string().min(1, { message: 'Title cannot be empty' }).trim().optional(),
  content: z.array(z.any()).min(1, { message: 'Content cannot be empty' }).optional(), // Basic check for non-empty array
  folderId: z.string().cuid({ message: 'Invalid folder ID format' }).optional().nullable(), // Allow setting to null
}).partial().refine(data => Object.keys(data).length > 0, {
  message: 'At least one field (title, content, folderId) must be provided for update',
});

// Helper function to verify ownership
async function verifyCardOwnership(userId: string, cardId: string) {
  const card = await prisma.knowledgeCard.findUnique({
    where: { id: cardId },
  });
  if (!card) {
    return { error: NextResponse.json({ message: 'Card not found' }, { status: 404 }), card: null };
  }
  if (card.userId !== userId) {
    return { error: NextResponse.json({ message: 'Forbidden' }, { status: 403 }), card: null };
  }
  return { error: null, card: card };
}

// --- GET Handler (Get Specific Card) ---
export async function GET(request: NextRequest, { params }: { params: { cardId: string } }) {
  const session = await getServerSession(authOptions);

  if (!session || !session.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // --- Fix: Await params --- 
  const resolvedParams = await params;
  console.log("[GET /api/cards/[cardId]] Resolved params:", resolvedParams); // Optional logging
  // --- End Fix ---

  try {
    // Get cardId using the resolved params
    const cardId = resolvedParams.cardId;
    if (!cardId) {
      return NextResponse.json({ error: 'Card ID is required' }, { status: 400 });
    }
    console.log(`[GET /api/cards/[cardId]] cardId: ${cardId}`); // Optional logging

    const card = await prisma.knowledgeCard.findUnique({
      where: {
        id: cardId,
        userId: session.user.id, // Ensure user owns the card
      },
      include: {
        folder: true, // Include full folder data if needed
        tags: true,   // Include full tag data if needed
      },
    });

    if (!card) {
      return NextResponse.json({ error: 'Card not found or access denied' }, { status: 404 });
    }

    return NextResponse.json(card);

  } catch (error) {
    console.error('Error fetching card:', error);
    return NextResponse.json({ error: 'Failed to fetch card' }, { status: 500 });
  }
}

// --- PUT Handler (Update Specific Card) ---
export async function PUT(req: NextRequest, context: { params: { cardId: string } }) {
  console.log("[PUT /api/cards/] Handler Entered");

  // Log the raw context object before validation
  console.log("[PUT /api/cards/] Raw context received:", context);

  // WORKAROUND: Await the params object as it seems to be a Promise
  let resolvedParams;
  try {
    resolvedParams = await context.params;
    console.log("[PUT /api/cards/] Resolved params:", resolvedParams);
  } catch (err) {
    console.error("Error awaiting context.params:", err);
    return NextResponse.json({ error: 'Failed to resolve route parameters' }, { status: 500 });
  }

  // Validate route parameters using the new schema and the RESOLVED params
  const contextValidation = RouteContextSchema.safeParse({ params: resolvedParams }); // Validate { params: resolved_object }
  if (!contextValidation.success) {
    // Log this failure
    console.error("Route context validation failed (after await):", contextValidation.error.format());
    return NextResponse.json({ errors: contextValidation.error.format() }, { status: 400 });
  }
  // Extract cardId after successful validation
  const { cardId } = contextValidation.data.params;

  // Check authentication
  const userId = await getCurrentUserId();
  console.log(`[PUT /api/cards/${cardId}] Authenticated userId:`, userId);
  if (!userId) {
    console.error("User ID not found, returning 401");
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Validate request body
  let validatedData;
  let body; // Define body outside try block
  try {
    body = await req.json(); // Could fail here -> Exit 3 (400)
    console.log("[PUT /api/cards/] Request body parsed:", body); // Add log here

    const validation = UpdateCardSchema.safeParse(body);
    if (!validation.success) {
      // Log this failure
      console.error("Request body validation failed:", validation.error.format());
      return NextResponse.json({ errors: validation.error.format() }, { status: 400 }); // Exit 2 (400)
    }
    console.log("[PUT /api/cards/] Request body validated successfully."); // Add log here
    validatedData = validation.data;
  } catch (error) {
     // Log this failure
    console.error("Error parsing request body:", error);
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 }); // Exit 3 (400)
  }

  try {
    // Verify user owns the card they are trying to update
    const existingCard = await prisma.knowledgeCard.findUnique({
      where: { id: cardId, userId: userId },
      select: { id: true },
    });

    if (!existingCard) {
      return NextResponse.json({ error: 'Card not found or not owned by user' }, { status: 404 });
    }

    // Add target folder ownership check if folderId is being updated
    if (validatedData.folderId !== undefined && validatedData.folderId !== null) {
        // Log the userId right before the check
        console.log(`Checking folder ownership: folderId=${validatedData.folderId}, userId=${userId}`);

        const targetFolder = await prisma.folder.findUnique({
          where: { id: validatedData.folderId, userId: userId }, // Check ownership
          select: { id: true },
        });
        if (!targetFolder) {
          return NextResponse.json({ error: 'Target folder not found or not owned by user' }, { status: 400 });
        }
    }

    // Prepare update data (only include validated fields)
    const updateData: Prisma.KnowledgeCardUpdateInput = {};
    if (validatedData.title !== undefined) updateData.title = validatedData.title;
    if (validatedData.content !== undefined) updateData.content = validatedData.content;
    if (validatedData.folderId !== undefined) updateData.folderId = validatedData.folderId; // Can be null

    // *** TODO: Handle Tag updates similar to KC-CARD-BE-2-BLOCK if tags are part of the update ***
    // if (validatedData.tags !== undefined) {
    //   const tagConnections = await getTagConnectionsForUpsert(validatedData.tags);
    //   updateData.tags = { set: [], connectOrCreate: tagConnections };
    // }

    // Attempt to update the card
    const updatedCard = await prisma.knowledgeCard.update({
      where: {
        id: cardId,
      },
      data: updateData,
      include: { tags: true, folder: true }, // Include related data in response
    });

    return NextResponse.json(updatedCard);

  } catch (error) {
    // Handle potential errors like foreign key constraints if folderId is invalid
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      if (error.code === 'P2003') { // Foreign key constraint failed
         // This might occur if folderId is invalid AFTER the ownership check (race condition?)
         // Or if other foreign key constraints fail
         return NextResponse.json({ error: 'Invalid related data (e.g., folder ID)' }, { status: 400 });
      }
       // Add other specific Prisma error codes if needed
    }

    // Log unexpected errors
    console.error('Failed to update card:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}

// --- DELETE Handler (Delete Specific Card) ---
export async function DELETE(req: NextRequest, { params }: RouteParams) {
  // Validate route parameters
  const paramsValidation = RouteContextSchema.safeParse({ params }); // Validate the structure { params: ... }
  if (!paramsValidation.success) {
    return NextResponse.json({ errors: paramsValidation.error.format() }, { status: 400 });
  }
  const { cardId } = paramsValidation.data.params;

  // Check authentication
  const userId = await getCurrentUserId();
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    // Verify ownership first
    const existingCard = await prisma.knowledgeCard.findUnique({
        where: { id: cardId, userId: userId },
        select: { id: true }
    });

    if (!existingCard) {
        return NextResponse.json({ error: 'Card not found or not owned by user' }, { status: 404 });
    }

    // Proceed with deletion
    await prisma.knowledgeCard.delete({
      where: { id: cardId },
    });

    // Return success response
    return NextResponse.json({ message: 'Card deleted successfully' }, { status: 200 });

  } catch (err) {
    console.error('Delete Card [id] Error:', err);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
} 