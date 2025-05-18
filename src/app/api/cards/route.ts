import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path as necessary
import prisma from '@/lib/prisma'; // Use default import
import { Prisma } from '@prisma/client'; // Import Prisma

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
  } catch (error: unknown) {
    console.error('Failed to fetch cards:', error);
    console.timeEnd('[GET /api/cards] Total Handler');
    return NextResponse.json(
      { error: 'Internal Server Error', details: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}

// Interface for the expected structure of individual image metadata objects from the frontend
interface ImageMetadataInput {
  appServedUrl: string; // Changed from url to appServedUrl
  gcsPath: string;
  contentType: string;
  originalFilename: string;
  size: number;
  userId: string; // userId is also part of UploadApiResponse and might be useful here
}

// Interface for the expected request body for creating a card
interface CreateCardRequestBody {
  title: string;
  content: any; // BlockNote editor content (JSON)
  tags?: string[]; // Array of tag names/IDs. Assuming tag names for simplicity here.
                  // If using IDs, ensure they exist or handle creation.
  imageMetadata?: ImageMetadataInput[]; // Uses updated ImageMetadataInput
  folderId?: string | null; // Optional: if cards can be added to folders
}

export async function POST(request: NextRequest) {
  const session = await getServerSession(authOptions);

  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  const userId = session.user.id;

  try {
    const body = await request.json() as CreateCardRequestBody;
    const {
      title,
      content,
      tags = [],
      imageMetadata = [],
      folderId = null,
    } = body;

    // console.log('POST /api/cards - Received imageMetadata from client:', JSON.stringify(imageMetadata, null, 2)); // Removed for cleanup

    if (!title || !content) {
      return NextResponse.json(
        { error: 'Title and content are required' },
        { status: 400 }
      );
    }

    // Handle tags: Find existing tags or create new ones
    // This is a common pattern. Adjust if your tag handling is different.
    const tagOperations = tags.map((tagName) => {
      const cleanTagName = tagName.startsWith('#') ? tagName.substring(1) : tagName;
      return prisma.tag.upsert({
        where: { name: cleanTagName.toLowerCase() }, // Ensure unique tag names, perhaps case-insensitive
        update: {},
        create: { name: cleanTagName.toLowerCase() },
      });
    });
    const upsertedTags = await Promise.all(tagOperations);

    // Use a Prisma transaction to ensure atomicity
    const newCard = await prisma.$transaction(async (tx) => {
      const card = await tx.knowledgeCard.create({
        data: {
          title,
          content,
          userId,
          folderId: folderId ? folderId : undefined, // Handle optional folderId
          tags: {
            connect: upsertedTags.map((tag) => ({ id: tag.id })),
          },
        },
      });

      if (imageMetadata.length > 0) {
        const imageMetadataToCreate = imageMetadata.map((meta) => {
          // console.log('POST /api/cards - Preparing ImageMetadata with gcsPath:', meta.gcsPath); // Removed for cleanup
          return {
            knowledgeCardId: card.id,
            userId, 
            gcsPath: meta.gcsPath,
            contentType: meta.contentType,
            originalFilename: meta.originalFilename,
            size: meta.size,
            appServedUrl: meta.appServedUrl, // Corrected to use meta.appServedUrl
          };
        });

        // console.log('POST /api/cards - imageMetadataToCreate (before createMany):', JSON.stringify(imageMetadataToCreate, null, 2)); // Removed for cleanup

        await tx.imageMetadata.createMany({
          data: imageMetadataToCreate,
        });
      }
      // Refetch card with tags to return it in the response, if needed by frontend
      // Or just return basic card data if that's sufficient
      return tx.knowledgeCard.findUnique({
        where: { id: card.id },
        include: { tags: true }, // Example: include tags in the response
      });
    });

    return NextResponse.json(newCard, { status: 201 });

  } catch (error: unknown) {
    console.error('Failed to create card:', error);
    if (error instanceof Prisma.PrismaClientKnownRequestError) {
      // Handle specific Prisma errors if necessary (e.g., unique constraint violation)
      if (error.code === 'P2002') { // Example: Unique constraint failed
        return NextResponse.json(
          { error: 'A card with this identifier already exists.' }, // Adjust message as needed
          { status: 409 }, // Conflict
        );
      }
      // Add other specific Prisma error codes as needed
    }
    // Generic error for other cases
    return NextResponse.json(
      { error: 'Internal Server Error', details: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}
