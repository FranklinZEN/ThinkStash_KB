import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

const AI_WORKER_URL = process.env.AI_WORKER_URL || 'http://localhost:8000';

export async function GET(
  req: Request,
  { params }: { params: { taskId: string } },
) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return new NextResponse('Unauthorized', { status: 401 });
    }

    const { taskId } = params;
    if (!taskId) {
      return new NextResponse('Task ID is required', { status: 400 });
    }

    const response = await fetch(`${AI_WORKER_URL}/tasks/${taskId}/status`);

    if (!response.ok) {
      const errorBody = await response.text();
      console.error(
        `Failed to get task status from AI worker for task ${taskId}:`,
        response.status,
        errorBody,
      );
      return new NextResponse(
        `Error from AI service: ${errorBody}`,
        { status: response.status },
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error in task status proxy:', error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
} 