import { NextResponse } from 'next/server';
import { getServerSession } from "next-auth/next";
import { authOptions } from '@/lib/auth';
import { prisma } from '@/lib/prisma';

export async function PUT(
  request: Request,
  { params }: { params: { cardId: string } }
) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userId = session.user.id;

    const cardId = params.cardId;
    if (!cardId) {
      return NextResponse.json({ error: 'Card ID is required' }, { status: 400 });
    }

    // Parse the target folderId from the request body
    let body: { folderId: string | null };
    try {
      body = await request.json();
    } catch (e) {
      return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
    }
    const targetFolderId = body.folderId;

    // 1. Verify the target folder exists and belongs to the user (if not null)
    if (targetFolderId !== null) {
      const targetFolder = await prisma.folder.findUnique({
        where: { id: targetFolderId, userId: userId },
        select: { id: true } // Only need to select ID to confirm existence and ownership
      });
      if (!targetFolder) {
        return NextResponse.json({ error: 'Target folder not found or access denied' }, { status: 404 });
      }
    }

    // 2. Verify the card exists and belongs to the user
    const card = await prisma.knowledgeCard.findUnique({
        where: { id: cardId, userId: userId },
        select: { id: true } // Only need ID
    });

    if (!card) {
        return NextResponse.json({ error: 'Card not found or access denied' }, { status: 404 });
    }

    // 3. Update the card's folderId
    const updatedCard = await prisma.knowledgeCard.update({
      where: { id: cardId }, // Already verified ownership above
      data: { folderId: targetFolderId },
      select: { id: true, folderId: true } // Return relevant fields
    });

    return NextResponse.json(updatedCard);

  } catch (error) {
    console.error('Error moving card:', error);
    return NextResponse.json(
      { error: 'Failed to move card' },
      { status: 500 }
    );
  }
} 