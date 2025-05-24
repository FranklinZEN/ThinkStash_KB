import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path as necessary
import prisma from '@/lib/prisma'; // Use default import
import { Prisma } from '@prisma/client'; // Import Prisma
import { handleCardImageAssociations } from '@/lib/services/cardService'; // Corrected import path
import { z } from 'zod';
import { CardContentSchema } from '@/lib/validators/editorValidators';

// --- GET Handler (List Cards) ---
export async function GET(req: NextRequest) {
  console.time('[GET /api/cards] Total Handler');
  console.time('[GET /api/cards] Session Check');
  const session = await getServerSession(authOptions);
  console.timeEnd('[GET /api/cards] Session Check');

  if (!session || !session.user?.id) {
    console.timeEnd('[GET /api/cards] Total Handler');
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  try {
    const userId = session.user.id;
    const { searchParams } = req.nextUrl; // Use req.nextUrl for App Router

    const page = parseInt(searchParams.get('page') || '1', 10);
    const pageSize = parseInt(searchParams.get('pageSize') || '20', 10);

    if (isNaN(page) || page < 1) {
      console.timeEnd('[GET /api/cards] Total Handler');
      return NextResponse.json(
        { message: 'Invalid page number' },
        { status: 400 },
      );
    }
    if (isNaN(pageSize) || pageSize < 1 || pageSize > 100) {
      // Max pageSize limit
      console.timeEnd('[GET /api/cards] Total Handler');
      return NextResponse.json(
        { message: 'Invalid pageSize (must be 1-100)' },
        { status: 400 },
      );
    }

    const skip = (page - 1) * pageSize;

    console.time('[GET /api/cards] Prisma Queries (findMany + count)');
    const [cards, totalCards] = await prisma.$transaction([
      prisma.knowledgeCard.findMany({
        where: {
          userId: userId,
        },
        orderBy: [{ isStarred: 'desc' }, { updatedAt: 'desc' }],
        select: {
          id: true,
          title: true,
          userId: true,
          folderId: true,
          isStarred: true,
          createdAt: true,
          updatedAt: true,
          content: true,
          folder: {
            select: {
              id: true,
              name: true,
            },
          },
          tags: {
            select: {
              name: true,
            },
          },
        },
        skip: skip,
        take: pageSize,
      }),
      prisma.knowledgeCard.count({
        where: {
          userId: userId,
        },
      }),
    ]);
    console.timeEnd('[GET /api/cards] Prisma Queries (findMany + count)');
    console.timeEnd('[GET /api/cards] Total Handler');

    return NextResponse.json(
      {
        data: cards,
        pagination: {
          page,
          pageSize,
          totalItems: totalCards,
          totalPages: Math.ceil(totalCards / pageSize),
        },
      },
      { status: 200 },
    );
  } catch (error) {
    console.error('Get Cards Error:', error);
    console.timeEnd('[GET /api/cards] Total Handler');
    return NextResponse.json(
      { message: 'Internal Server Error' },
      { status: 500 },
    );
  } finally {
    // await prisma.$disconnect(); // Singleton pattern
  }
}

// --- Zod Schema for POST Request Body ---
const CreateCardPayloadSchema = z.object({
  title: z.string().trim().min(1, { message: 'Title is required.' }),
  content: CardContentSchema.optional(), // Content is BlockNote JSON, can be empty array for new card
  folderId: z
    .string()
    .cuid({ message: 'Invalid folder ID format.' })
    .optional()
    .nullable(),
  tags: z.array(z.string().trim().min(1)).optional(),
});

// --- POST Handler (Create Card) ---
export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session || !session.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await req.json();
    const validationResult = CreateCardPayloadSchema.safeParse(body);

    if (!validationResult.success) {
      return NextResponse.json(
        {
          error: 'Invalid request payload',
          details: validationResult.error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }

    const { title, content, folderId, tags } = validationResult.data;

    // Validate folderId ownership if provided (and not null)
    if (folderId) {
      const folder = await prisma.folder.findFirst({
        where: { id: folderId, userId: session.user.id },
      });
      if (!folder) {
        return NextResponse.json(
          { error: 'Folder not found or access denied.' },
          { status: 404 },
        );
      }
    }

    // Initial content for creation (will be processed for images shortly)
    const initialContentForDb = content || [];

    const createData: Prisma.KnowledgeCardCreateInput = {
      title,
      content: initialContentForDb, // Store the initial valid content (e.g., BlockNote JSON)
      user: {
        connect: { id: session.user.id },
      },
    };

    if (tags && tags.length > 0) {
      createData.tags = {
        connectOrCreate: tags.map((tagName) => ({
          where: { name: tagName },
          create: { name: tagName },
        })),
      };
    }

    if (folderId) {
      createData.folder = { connect: { id: folderId } };
    }

    // 1. Create the card with initial content
    const newCard = await prisma.knowledgeCard.create({
      data: createData,
      include: {
        tags: true,
        folder: true,
      },
    });

    let finalContentForDb = newCard.content; // Default to what was just created
    let cardDataForResponse = { ...newCard };

    // 2. Process content for image associations (if content exists)
    if (
      initialContentForDb && // Use the content that was intended for the DB
      Array.isArray(initialContentForDb) &&
      initialContentForDb.length > 0
    ) {
      try {
        const imageAssociationResult = await handleCardImageAssociations(
          initialContentForDb,
          newCard.id,
          session.user.id,
        );

        // If processedContent is null or undefined, default to an empty array,
        // which is a valid Prisma.JsonValue for BlockNote content.
        finalContentForDb = imageAssociationResult.processedContent ?? [];

        // Update the card with the processed content (which might have new appServedUrls)
        // and link active images
        if (finalContentForDb) {
          // Ensure finalContentForDb is not null/undefined
          const updatedCardWithProcessedContent =
            await prisma.knowledgeCard.update({
              where: { id: newCard.id },
              data: { content: finalContentForDb }, // Save the actual BlockNoteDocument
              include: {
                tags: true,
                folder: true,
              },
            });
          cardDataForResponse = { ...updatedCardWithProcessedContent }; // Update response data
          console.log(
            `[POST /api/cards] Updated card ${newCard.id} with processed image content in DB.`,
          );
        } else {
          // This case implies image processing resulted in empty/null content, which should be handled.
          // For now, we assume processedContent would be at least an empty array if input was valid.
          console.warn(
            `[POST /api/cards] Image processing for ${newCard.id} resulted in null/undefined content. Original content (or empty array) remains in DB.`,
          );
          // Ensure cardDataForResponse.content is consistent if it became null
          if (
            finalContentForDb === null &&
            cardDataForResponse.content !== null
          ) {
            cardDataForResponse.content = null;
          }
        }

        // Link active images found during processing
        if (imageAssociationResult.activeImageRecordIds.length > 0) {
          await prisma.imageRecord.updateMany({
            where: {
              id: { in: imageAssociationResult.activeImageRecordIds },
              userId: session.user.id,
            },
            data: { knowledgeCardId: newCard.id },
          });
          console.log(
            `[POST /api/cards] Linked ${imageAssociationResult.activeImageRecordIds.length} images to new card ${newCard.id}.`,
          );
        }
      } catch (imageError) {
        console.error(
          `[POST /api/cards] Error processing images for new card ${newCard.id}:`,
          imageError,
        );
        // Card is already created, but image processing failed.
        // The cardDataForResponse will contain the initially created card.
      }
    } else {
      console.log(
        `[POST /api/cards] No initial content provided for card ${newCard.id}, skipping image processing.`,
      );
    }
    // Ensure the content in the response is the final processed content
    // This step is crucial if cardDataForResponse was not updated due to image processing failing or content being null
    if (cardDataForResponse.content !== finalContentForDb) {
      // This check is a bit tricky because newCard.content is Prisma.JsonValue
      // and finalContentForDb can also be Prisma.JsonValue. An explicit update might be safer.
      cardDataForResponse = {
        ...cardDataForResponse,
        content: finalContentForDb, // Set the correct content for the response
      };
    }

    return NextResponse.json(cardDataForResponse, { status: 201 });
  } catch (error) {
    console.error('Error creating card:', error);
    if (error instanceof SyntaxError) {
      return NextResponse.json(
        { error: 'Invalid JSON in request body' },
        { status: 400 },
      );
    }
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      if (error.code === 'P2002') {
        return NextResponse.json(
          {
            error:
              'A database error occurred (e.g., unique constraint failed).',
          },
          { status: 409 },
        );
      }
    }
    return NextResponse.json(
      { error: 'Failed to create card' },
      { status: 500 },
    );
  }
}
