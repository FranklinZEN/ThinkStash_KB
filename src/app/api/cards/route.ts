import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path as necessary
import { prisma } from '@/lib/prisma'; // Adjust path as necessary

// --- GET Handler (List Cards) ---
export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);

  if (!session || !session.user?.id) {
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  try {
    const userId = session.user.id;

    // TODO: Add filtering (e.g., by folderId) and pagination from query params later
    // const { searchParams } = new URL(req.url);
    // const folderIdFilter = searchParams.get('folderId');

    const cards = await prisma.knowledgeCard.findMany({
      where: {
        userId: userId,
        // Add folderId to where clause if filtering
        // ...(folderIdFilter && { folderId: folderIdFilter }),
      },
      orderBy: [
        { isStarred: 'desc' }, // Sort by starred first
        { updatedAt: 'desc' }  // Then by most recently updated
      ],
      include: {
        folder: {
          select: {
            id: true,
            name: true
          }
        },
        tags: { // Also include tags if CardListItem uses them
          select: {
            name: true
          }
        }
      }
      // Select all fields implicitly now, including isStarred
    });

    return NextResponse.json(cards, { status: 200 });

  } catch (error) {
    console.error('Get Cards Error:', error);
    return NextResponse.json({ message: 'Internal Server Error' }, { status: 500 });
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
    const { title, content, folderId } = body;

    // --- Input Validation ---
    if (!title || typeof title !== 'string' || title.trim().length === 0) {
      return NextResponse.json({ message: 'Title is required and must be a non-empty string' }, { status: 400 });
    }

    if (content === undefined || content === null) { // Allow empty objects/arrays, but not missing
      return NextResponse.json({ message: 'Content is required' }, { status: 400 });
    }
    // Basic check if content is somewhat object-like (Prisma expects Json type)
    // More specific validation might be needed depending on expected content structure
    if (typeof content !== 'object') {
        return NextResponse.json({ message: 'Content must be a valid JSON object' }, { status: 400 });
    }

    if (folderId !== undefined && (typeof folderId !== 'string' || folderId.trim().length === 0)) {
      return NextResponse.json({ message: 'folderId must be a non-empty string if provided' }, { status: 400 });
    }
    // --- End Validation ---

    // Prepare data for Prisma create
    const data: any = {
      title: title.trim(),
      content: content, // Prisma expects JSON compatible object/value
      userId: userId,
    };

    // Add folderId only if it's provided and valid
    if (folderId) {
      // Optional: Check if the folder exists and belongs to the user
      const folder = await prisma.folder.findFirst({
        where: { id: folderId, userId: userId }
      });
      if (!folder) {
        return NextResponse.json({ message: 'Folder not found or access denied' }, { status: 404 });
      }
      data.folderId = folderId;
    }

    // Create the Knowledge Card
    const newCard = await prisma.knowledgeCard.create({
      data: data,
    });

    return NextResponse.json(newCard, { status: 201 });

  } catch (error: any) {
    console.error('Create Card Error:', error);
    // Handle potential Prisma errors (e.g., unique constraint violation? unlikely here)
    if (error.code === 'P2003') { // Foreign key constraint failed (e.g., invalid folderId)
        return NextResponse.json({ message: 'Invalid folderId provided' }, { status: 400 });
    }
    return NextResponse.json({ message: 'Internal Server Error' }, { status: 500 });
  } finally {
    // await prisma.$disconnect(); // Singleton pattern
  }
} 