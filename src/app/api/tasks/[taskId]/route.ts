import { NextResponse } from 'next/server';
import db from '@/lib/prisma';

export async function GET(
  request: Request,
  { params }: { params: { taskId: string } }
) {
  try {
    const { taskId } = params;

    const task = await db.task.findUnique({
      where: {
        id: taskId,
      },
      select: {
        id: true,
        status: true,
        result: true,
        type: true,
        error: true,
        progressMessage: true,
        createdAt: true,
        updatedAt: true,
      }
    });

    if (!task) {
      return new NextResponse('Task not found', { status: 404 });
    }

    return NextResponse.json(task);
  } catch (error) {
    console.error('[TASK_GET_API]', error);
    return new NextResponse('Internal Error', { status: 500 });
  }
} 