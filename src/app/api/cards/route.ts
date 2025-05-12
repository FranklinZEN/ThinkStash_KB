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
  const session = await getServerSession(authOptions);

  if (!session || !session.user?.id) {
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  try {
    const userId = session.user.id;
    const body = await req.json();
    const { title, content, folderId, tags } = body;

    // --- Input Validation ---
    if (!title || typeof title !== 'string' || title.trim().length === 0) {
      return NextResponse.json(
        { message: 'Title is required and must be a non-empty string' },
        { status: 400 },
      );
    }

    if (content === undefined || content === null) {
      // Allow empty objects/arrays, but not missing
      return NextResponse.json(
        { message: 'Content is required' },
        { status: 400 },
      );
    }
    // Basic check if content is somewhat object-like (Prisma expects Json type)
    // More specific validation might be needed depending on expected content structure
    if (typeof content !== 'object') {
      return NextResponse.json(
        { message: 'Content must be a valid JSON object' },
        { status: 400 },
      );
    }

    if (
      folderId !== undefined &&
      (typeof folderId !== 'string' || folderId.trim().length === 0)
    ) {
      return NextResponse.json(
        { message: 'folderId must be a non-empty string if provided' },
        { status: 400 },
      );
    }
    // Validate tags if provided (must be an array of strings)
    if (tags !== undefined && !Array.isArray(tags)) {
      return NextResponse.json(
        { message: 'Tags must be an array of strings' },
        { status: 400 },
      );
    }
    if (
      tags &&
      Array.isArray(tags) &&
      !tags.every((tag) => typeof tag === 'string')
    ) {
      return NextResponse.json(
        { message: 'All tags in the array must be strings' },
        { status: 400 },
      );
    }
    // --- End Validation ---

    // Prepare data for Prisma create
    const data: Prisma.KnowledgeCardCreateInput = {
      title: title.trim(),
      content: content, // Prisma expects JSON compatible object/value
      user: {
        // Connect to the existing user via the relation field
        connect: { id: userId },
      },
      // Add tags if provided
      ...(tags &&
        Array.isArray(tags) &&
        tags.length > 0 && {
          tags: {
            connectOrCreate: tags.map((tagName: string) => ({
              where: { name: tagName.trim() },
              create: { name: tagName.trim() },
            })),
          },
        }),
    };

    // Add folderId only if it's provided and valid
    if (folderId) {
      // Optional: Check if the folder exists and belongs to the user
      const folder = await prisma.folder.findFirst({
        where: { id: folderId, userId: userId },
      });
      if (!folder) {
        return NextResponse.json(
          { message: 'Folder not found or access denied' },
          { status: 404 },
        );
      }
      data.folder = { connect: { id: folderId } }; // New way: connect via relation
    }

    // Create the Knowledge Card
    const newCard = await prisma.knowledgeCard.create({
      data: data,
      include: {
        // Explicitly include tags and folder in the response
        tags: true,
        folder: true,
      },
    });

    return NextResponse.json(newCard, { status: 201 });
  } catch (error: unknown) {
    console.error('Create Card Error:', error);
    // Handle potential Prisma errors (e.g., unique constraint violation? unlikely here)
    // Check if error is a Prisma error with a code property
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === 'P2003'
    ) {
      // Foreign key constraint failed (e.g., invalid folderId)
      return NextResponse.json(
        { message: 'Invalid folderId provided' },
        { status: 400 },
      );
    }
    return NextResponse.json(
      { message: 'Internal Server Error' },
      { status: 500 },
    );
  } finally {
    // await prisma.$disconnect(); // Singleton pattern
  }
}
