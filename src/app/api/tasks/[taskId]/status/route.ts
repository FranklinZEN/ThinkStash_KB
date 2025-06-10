import prisma from '@/lib/prisma';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { NextResponse } from 'next/server';

export async function GET(req: Request, { params }: { params: { taskId: string } }) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return new NextResponse('Unauthorized', { status: 401 });
    }

    const { taskId } = params;
    const task = await prisma.task.findFirst({
      where: {
        id: taskId,
        userId: session.user.id,
      }
    });

    if (!task) {
      return new NextResponse('Task not found', { status: 404 });
    }

    return NextResponse.json(task);
  } catch (error) {
    console.error(`Failed to fetch task status for ${params.taskId}:`, error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
} 