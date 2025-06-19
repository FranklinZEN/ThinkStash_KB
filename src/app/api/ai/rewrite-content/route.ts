import { Prisma } from '@prisma/client';
import prisma from '@/lib/prisma';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { NextResponse } from 'next/server';
import { v4 as uuidv4 } from 'uuid';
import type { RewriteContentRequest } from '@/types/api/ai-service';

// Define the expected structure of the successful response from the AI service
interface AIServiceSuccessResponse {
  message: string;
  task_id: string;
}

export async function POST(req: Request) {
  const correlationId = uuidv4();
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return new NextResponse('Unauthorized', { status: 401 });
    }

    const body = (await req.json()) as RewriteContentRequest;
    // The backend task expects 'content_blocks'
    const { content_blocks_to_rewrite, document_metadata } = body;

    if (
      !content_blocks_to_rewrite ||
      !Array.isArray(content_blocks_to_rewrite) ||
      content_blocks_to_rewrite.length === 0
    ) {
      return NextResponse.json(
        {
          error:
            'Invalid request body: content_blocks_to_rewrite is required and must be a non-empty array.',
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
          task_type: 'REWRITE_CONTENT',
          user_id: session.user.id,
          payload: {
            // Send as 'content_blocks' to match backend expectation
            content_blocks: content_blocks_to_rewrite,
            document_metadata: document_metadata,
            correlationId: correlationId,
          },
        }),
      },
    );

    if (!aiServiceResponse.ok) {
      const errorBody = await aiServiceResponse.text();
      console.error(
        `Failed to dispatch rewrite task. Status: ${aiServiceResponse.status}, Body: ${errorBody}`,
        { correlationId },
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
    console.error('Failed to create rewrite task:', {
      correlationId,
      errorDetails:
        error instanceof Error
          ? { message: error.message, stack: error.stack }
          : { message: String(error) },
    });
    return new NextResponse('Internal Server Error', { status: 500 });
  }
}
