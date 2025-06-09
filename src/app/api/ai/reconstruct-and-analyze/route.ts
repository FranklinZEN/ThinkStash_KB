import prisma from '@/lib/prisma';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return new NextResponse('Unauthorized', { status: 401 });
    }

    const body = await req.json();
    const { sourceUrl } = body;

    if (!sourceUrl) {
      return new NextResponse('Source URL is required', { status: 400 });
    }

    const task = await prisma.task.create({
      data: {
        userId: session.user.id,
        type: 'RECONSTRUCT_AND_ANALYZE',
        status: 'PENDING',
        payload: { sourceUrl },
        progress: 5, // Start with a small amount of progress
        progressMessage: 'Task created and awaiting processing.',
      },
    });

    return NextResponse.json({ taskId: task.id }, { status: 202 });
  } catch (error) {
    console.error('Failed to create task:', error);
    // In case of a database error or other server issue
    return new NextResponse('Internal Server Error', { status: 500 });
  }
} 