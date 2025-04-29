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

    // Get current card to check ownership and current star status
    const card = await prisma.knowledgeCard.findUnique({
      where: { id: cardId, userId },
      select: { id: true, isStarred: true }
    });

    if (!card) {
      return NextResponse.json({ error: 'Card not found' }, { status: 404 });
    }

    // Toggle the star status
    const updatedCard = await prisma.knowledgeCard.update({
      where: { id: cardId },
      data: { isStarred: !card.isStarred },
      select: { id: true, isStarred: true }
    });

    return NextResponse.json(updatedCard);
  } catch (error) {
    console.error('Error toggling card star status:', error);
    return NextResponse.json(
      { error: 'Failed to toggle star status' },
      { status: 500 }
    );
  }
} 