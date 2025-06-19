import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { NextResponse } from 'next/server';
import { z } from 'zod';

const AI_WORKER_URL = process.env.AI_WORKER_URL || 'http://localhost:8000';

const DraftRequestSchema = z.object({
  sourceUrl: z.string().url(),
  save_to_db: z.boolean().optional(),
});

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return new NextResponse('Unauthorized', { status: 401 });
    }

    const body = await req.json();
    const validation = DraftRequestSchema.safeParse(body);

    if (!validation.success) {
      return new NextResponse(JSON.stringify(validation.error.format()), {
        status: 400,
      });
    }

    const { sourceUrl, save_to_db } = validation.data;

    const createTaskPayload = {
      task_type: 'RECONSTRUCT_AND_ANALYZE',
      user_id: session.user.id,
      payload: {
        sourceUrl: sourceUrl,
        source_type: 'url',
        run_title_generation: true,
        // Default to TRUE if save_to_db is not provided or is null
        save_to_db: save_to_db !== false,
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
      console.error(
        'Failed to create and dispatch task:',
        response.status,
        errorBody,
      );
      return new NextResponse(`Error from AI service: ${errorBody}`, {
        status: response.status,
      });
    }

    const responseData = await response.json();

    return NextResponse.json({ taskId: responseData.task_id }, { status: 202 });
  } catch (error) {
    console.error('Failed to create draft task:', error);
    if (error instanceof z.ZodError) {
      return new NextResponse(JSON.stringify(error.issues), { status: 400 });
    }
    return new NextResponse('Internal Server Error', { status: 500 });
  }
} 