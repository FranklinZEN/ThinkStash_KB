import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function POST(request: Request) {
  try {
    const { folders } = await request.json();

    // Update the order of each folder
    const updates = folders.map((folder: { id: string; order: number }) => {
      return prisma.folder.update({
        where: { id: folder.id },
        data: { order: folder.order },
      });
    });

    await prisma.$transaction(updates);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error reordering folders:', error);
    return NextResponse.json(
      { error: 'Failed to reorder folders' },
      { status: 500 }
    );
  }
} 