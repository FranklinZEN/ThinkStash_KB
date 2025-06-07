import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path as necessary
import prisma from '@/lib/prisma';
import { Prisma } from '@prisma/client'; // Import Prisma directly from @prisma/client
import { z } from 'zod'; // Re-add Zod import
import { CardContentSchema } from '@/lib/validators/editorValidators'; // Re-add CardContentSchema import
// import { Prisma } from '@prisma/client'; // Removed
// import { handleCardImageAssociations } from '@/lib/services/cardImageService'; // Removed
// import { CardContentSchema } from '@/lib/validators/editorValidators'; // Removed unused import
import type {
  // CreateCardRequest, // Removed unused import
  KnowledgeCardResponse,
  // ContentBlock, // Removed unused import
} from '@/types/api/ai-service';

// Zod schema for validating the POST request body
const CreateCardBodySchema = z.object({
  title: z.string().min(1, { message: 'Title cannot be empty' }).trim(),
  content: CardContentSchema, // Use the imported schema for BlockNote content
  folderId: z
    .string()
    .cuid({ message: 'Invalid folder ID format.' })
    .nullable()
    .optional(),
  tags: z
    .array(z.string().trim().min(1, { message: 'Tag name cannot be empty.' }))
    .optional(),
  isStarred: z.boolean().optional(),
});

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

// --- POST Handler (Create Card) ---
export async function POST(req: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userId = session.user.id;

    const rawBody = await req.json();
    const validationResult = CreateCardBodySchema.safeParse(rawBody);

    if (!validationResult.success) {
      return NextResponse.json(
        {
          error: 'Invalid request body',
          details: validationResult.error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }

    const { title, content, folderId, tags, isStarred } = validationResult.data;

    // console.log('API /cards (POST) called to create card with title:', title); // Keep for debugging if needed

    const newCardId = await prisma.$transaction(async (tx) => {
      const tagConnections: { id: string }[] = [];
      if (tags && tags.length > 0) {
        for (const tagName of tags) {
          const tag = await tx.tag.upsert({
            where: { name: tagName },
            update: { name: tagName },
            create: { name: tagName },
          });
          tagConnections.push({ id: tag.id });
        }
      }

      const cardData: Prisma.KnowledgeCardCreateInput = {
        user: { connect: { id: userId } },
        title,
        content: content as Prisma.InputJsonValue,
        isStarred: isStarred || false,
      };

      if (folderId) {
        cardData.folder = { connect: { id: folderId } };
      }

      if (tagConnections.length > 0) {
        cardData.tags = { connect: tagConnections };
      }

      const createdCard = await tx.knowledgeCard.create({
        data: cardData,
      });

      // Image association logic
      if (content && Array.isArray(content)) {
        for (const block of content as {
          type: string;
          props?: { url?: string };
        }[]) {
          if (block.type === 'image' && block.props?.url) {
            const imageUrl = block.props.url as string;
            const parts = imageUrl.split('/');
            const imageRecordId = parts.pop();

            if (imageRecordId) {
              try {
                await tx.imageRecord.updateMany({
                  where: {
                    id: imageRecordId,
                    userId: userId,
                    knowledgeCardId: null,
                  },
                  data: { knowledgeCardId: createdCard.id },
                });
              } catch (imgError) {
                console.error(
                  `Failed to associate imageRecord ${imageRecordId} with card ${createdCard.id}:`,
                  imgError,
                );
              }
            }
          }
        }
      }
      return createdCard.id; // Return only the ID from the transaction
    });

    // After transaction, fetch the full card with all relations
    const fullyPopulatedCard = await prisma.knowledgeCard.findUnique({
      where: { id: newCardId },
      include: {
        folder: true,
        tags: true,
        imageRecords: true, // This should now pick up the linked records
      },
    });

    if (!fullyPopulatedCard) {
      console.error(`Failed to re-fetch created card with id: ${newCardId}`);
      return NextResponse.json(
        { error: 'Failed to retrieve created card after creation.' },
        { status: 500 },
      );
    }

    const responsePayload: KnowledgeCardResponse = {
      id: fullyPopulatedCard.id,
      title: fullyPopulatedCard.title,
      content: fullyPopulatedCard.content as Record<string, unknown>[],
      userId: fullyPopulatedCard.userId,
      folderId: fullyPopulatedCard.folderId,
      tags: fullyPopulatedCard.tags.map((tag) => ({
        id: tag.id,
        name: tag.name,
      })),
      createdAt: fullyPopulatedCard.createdAt.toISOString(),
      updatedAt: fullyPopulatedCard.updatedAt.toISOString(),
      isStarred: fullyPopulatedCard.isStarred,
      imageRecords: fullyPopulatedCard.imageRecords
        ? fullyPopulatedCard.imageRecords.map((ir) => ({
            id: ir.id,
            appServedUrl: ir.appServedUrl || '',
            gcsPath: ir.gcsPath || '',
            contentType: ir.contentType || '',
            originalFilename: ir.originalFilename || '',
            size: ir.size || 0,
          }))
        : [],
    };

    return NextResponse.json(responsePayload, { status: 201 });
  } catch (error) {
    console.error('Error in /cards (POST):', error);
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    // Handle Prisma-specific errors if needed, e.g., unique constraint violations
    if (error instanceof z.ZodError) {
      // Should be caught by safeParse, but as a fallback
      return NextResponse.json(
        {
          error: 'Validation error in POST.',
          details: error.flatten().fieldErrors,
        },
        { status: 400 },
      );
    }
    return NextResponse.json(
      { error: 'Failed to create card.', details: errorMessage },
      { status: 500 },
    );
  }
}

// Optional: GET /api/cards (to list cards for a user)
// export async function GET(req: NextRequest) {
//   try {
//     // const session = await auth();
//     // if (!session?.user?.id) {
//     //   return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
//     // }
//     // const userId = session.user.id;

//     // TODO: Implement logic to fetch and return a list of cards for the user.
//     // (Consider pagination, filtering, sorting)

//     console.log('API /cards (GET) called');
//     const mockListResponse: KnowledgeCardResponse[] = [];
//     return NextResponse.json(mockListResponse);
//   } catch (error) {
//     console.error('Error in /cards (GET):', error);
//     const errorMessage = error instanceof Error ? error.message : 'An unknown error occurred';
//     return NextResponse.json({ error: 'Failed to fetch cards.', details: errorMessage }, { status: 500 });
//   }
// }
