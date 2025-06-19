import { Prisma } from '@prisma/client';
import prisma from '@/lib/prisma';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { NextResponse } from 'next/server';
import type { GenerateKeywordsRequest } from '@/types/api/ai-service';

// Define the expected structure of the successful response from the AI service
interface AIServiceSuccessResponse {
  message: string;
  task_id: string;
}

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return new NextResponse('Unauthorized', { status: 401 });
    }

    const body = (await req.json()) as GenerateKeywordsRequest;
    const { content_blocks } = body;

    if (
      !content_blocks ||
      !Array.isArray(content_blocks) ||
      content_blocks.length === 0
    ) {
      return NextResponse.json(
        {
          error:
            'Invalid request body: content_blocks is required and must be a non-empty array.',
        },
        { status: 400 },
      );
    }

    const aiServiceResponse = await fetch(
      'http://localhost:8000/create-and-dispatch-task',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task_type: 'GENERATE_KEYWORDS',
          user_id: session.user.id,
          payload: {
            content_blocks: content_blocks,
          },
        }),
      },
    );

    if (!aiServiceResponse.ok) {
      const errorBody = await aiServiceResponse.text();
      console.error(
        `Failed to dispatch keyword generation task. Status: ${aiServiceResponse.status}, Body: ${errorBody}`,
      );
      return NextResponse.json(
        {
          error: 'Failed to communicate with AI service',
          details: errorBody,
        },
        { status: aiServiceResponse.status },
      );
    }

    const responseData =
      (await aiServiceResponse.json()) as AIServiceSuccessResponse;

    return NextResponse.json({ taskId: responseData.task_id }, { status: 202 });
  } catch (error) {
    console.error('Failed to create keyword generation task:', error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
}
