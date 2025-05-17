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
  const session = await getServerSession(authOptions); // --- REVERTED: Session check enabled ---

  if (!session || !session.user?.id) {
    // --- REVERTED: Session check enabled ---
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 }); // --- REVERTED: Session check enabled ---
  }

  try {
    const body = await req.json();
    const { title, tags, content, folderId } = body;

    // Basic validation for title and content
    if (!title || typeof title !== 'string' || title.trim().length === 0) {
      return NextResponse.json(
        { error: 'Title is required and must be a non-empty string.' },
        { status: 400 },
      );
    }
    if (!content) {
      // Assuming content can be an empty JSON object/array but must be present
      return NextResponse.json(
        { error: 'Content is required.' },
        { status: 400 },
      );
    }
    if (typeof content !== 'object') {
      // Basic check for JSON structure
      return NextResponse.json(
        { error: 'Content must be a valid JSON object or array.' },
        { status: 400 },
      );
    }

    // Validate tags: must be an array of non-empty strings if provided
    let validTags: string[] = [];
    if (tags !== undefined) {
      if (
        !Array.isArray(tags) ||
        !tags.every((tag) => typeof tag === 'string' && tag.trim().length > 0)
      ) {
        return NextResponse.json(
          { error: 'Tags must be an array of non-empty strings.' },
          { status: 400 },
        );
      }
      validTags = tags.map((tag) => tag.trim()).filter((tag) => tag.length > 0);
    }

    // Validate folderId if provided
    if (
      folderId !== undefined &&
      (typeof folderId !== 'string' || folderId.trim().length === 0)
    ) {
      return NextResponse.json(
        { error: 'folderId must be a non-empty string if provided.' },
        { status: 400 },
      );
    }

    const createData: Prisma.KnowledgeCardCreateInput = {
      title: title.trim(),
      content,
      user: {
        connect: { id: session.user.id }, // --- REVERTED: Use session.user.id ---
      },
    };

    if (validTags.length > 0) {
      createData.tags = {
        connectOrCreate: validTags.map((tagName) => ({
          where: { name: tagName },
          create: { name: tagName },
        })),
      };
    }

    if (folderId) {
      const folder = await prisma.folder.findFirst({
        where: { id: folderId, userId: session.user.id }, // --- REVERTED: Use session.user.id ---
      });
      if (!folder) {
        return NextResponse.json(
          { error: 'Folder not found or access denied.' },
          { status: 404 },
        ); // Message updated
      }
      createData.folder = { connect: { id: folderId } };
    }

    const newCard = await prisma.knowledgeCard.create({
      data: createData,
      include: {
        // Optionally include relations in the response
        tags: true,
        folder: true,
      },
    });

    return NextResponse.json(newCard, { status: 201 });
  } catch (error) {
    console.error('Error creating card:', error);
    if (error instanceof SyntaxError) {
      return NextResponse.json(
        { error: 'Invalid JSON in request body' },
        { status: 400 },
      );
    }
    // Check if the error is an instance of Prisma's known request error
    // This is a more robust way to check than error.code directly on an unknown type
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
      // You could add more specific Prisma error codes here if needed
    }
    return NextResponse.json(
      { error: 'Failed to create card' },
      { status: 500 },
    );
  } finally {
    // await prisma.$disconnect(); // Singleton pattern
  }
}
