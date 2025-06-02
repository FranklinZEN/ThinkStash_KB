import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path as necessary
import prisma from '@/lib/prisma'; // Use default import
// import { Prisma } from '@prisma/client'; // Removed
// import { handleCardImageAssociations } from '@/lib/services/cardImageService'; // Removed
// import { z } from 'zod'; // Removed unused import
// import { CardContentSchema } from '@/lib/validators/editorValidators'; // Removed unused import
import type {
  CreateCardRequest,
  KnowledgeCardResponse,
} from '@/types/api/ai-service';

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
    // const session = await auth();
    // if (!session?.user?.id) {
    //   return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    // }
    // const userId = session.user.id;

    const body = (await req.json()) as CreateCardRequest;
    const { title, content, folderId, tags, isStarred } = body;

    // TODO: Implement logic to create a new KnowledgeCard.
    // This will involve:
    // 1. Validating the input.
    // 2. Getting userId from session.
    // 3. Creating tags in the DB if they don't exist (or finding existing ones).
    // 4. Creating ImageRecord entries for images in content blocks (requires userId and new cardId).
    // 5. Creating the KnowledgeCard record in the database, linking to user, folder, tags, images.
    // 6. Returning the created KnowledgeCard.

    console.log('API /cards (POST) called to create card with title:', title);

    // Placeholder response (should be the created card data)
    const mockResponse: KnowledgeCardResponse = {
      id: 'mock-card-id-new',
      userId: 'mock-user-id', // Replace with actual userId from session
      title,
      content,
      folderId: folderId || undefined,
      tags: tags
        ? tags.map((tag) => ({ id: `mock-tag-${tag}`, name: tag }))
        : [],
      imageRecords: [], // Populate based on images in content
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      isStarred: isStarred || false,
    };

    return NextResponse.json(mockResponse, { status: 201 });
  } catch (error) {
    console.error('Error in /cards (POST):', error);
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
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
