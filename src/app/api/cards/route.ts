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
          { status: 404 }, // Or 400 if considered a bad request due to invalid folderId
        );
      }
    }

    const createData: Prisma.KnowledgeCardCreateInput = {
      title,
      content: content || [], // Default to empty array if content is undefined/null after validation
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

    let cardToReturn;
    const newCard = await prisma.knowledgeCard.create({
      data: createData,
      include: {
        tags: true,
        folder: true,
      },
    });

    cardToReturn = { ...newCard };

    // After creating the card, process its content for images
    // newCard.content here is the validated (and potentially defaulted to []) content
    if (
      newCard.content &&
      Array.isArray(newCard.content) &&
      newCard.content.length > 0
    ) {
      try {
        const modifiedContent = await handleCardImageAssociations(
          newCard.content, // Pass the potentially empty but validated content
          newCard.id,
          session.user.id,
        );

        // Only update if modifiedContent is different and not null/undefined
        if (
          modifiedContent &&
          JSON.stringify(modifiedContent) !== JSON.stringify(newCard.content)
        ) {
          const updatedCardWithProcessedImages =
            await prisma.knowledgeCard.update({
              where: { id: newCard.id },
              data: { content: modifiedContent },
              include: {
                tags: true,
                folder: true,
              },
            });
          cardToReturn = { ...updatedCardWithProcessedImages };
          console.log(
            `[POST /api/cards] Updated card ${newCard.id} with processed image content.`,
          );
        } else {
          console.log(
            `[POST /api/cards] Image associations checked for new card ${newCard.id}. No content modifications were necessary.`,
          );
        }
      } catch (imageError) {
        console.error(
          `[POST /api/cards] Error processing images for new card ${newCard.id}:`,
          imageError,
        );
      }
    }
    return NextResponse.json(cardToReturn, { status: 201 });
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
