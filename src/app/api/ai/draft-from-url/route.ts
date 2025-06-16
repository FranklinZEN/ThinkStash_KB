import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { NextResponse } from 'next/server';

const AI_WORKER_URL = process.env.AI_WORKER_URL || 'http://localhost:8000';

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

    // The payload for the backend endpoint that creates and dispatches
    const createTaskPayload = {
      // This is a generic type the backend understands
      task_type: 'RECONSTRUCT_AND_ANALYZE',
      user_id: session.user.id,
      // The payload specific to this task type
      payload: {
        url: sourceUrl,
        source_type: 'url',
      },
    };

    const response = await fetch(`${AI_WORKER_URL}/create-and-dispatch-task`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(createTaskPayload),
    });

    if (!response.ok) {
      const errorBody = await response.text();
      console.error('Failed to create and dispatch task:', response.status, errorBody);
      return new NextResponse(`Error from AI service: ${errorBody}`, { status: response.status });
    }

    const responseData = await response.json();

    // The backend returns the taskId it created
    return NextResponse.json({ taskId: responseData.task_id }, { status: 202 });
  } catch (error) {
    console.error('Failed to create draft task:', error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
} 