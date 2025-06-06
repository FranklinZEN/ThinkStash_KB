import { NextRequest, NextResponse } from 'next/server';
import type {
  RewriteContentRequest,
  // RewriteContentResponse, // This will now be simpler: { task_id: string }
} from '@/types/api/ai-service';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth';
import { v4 as uuidv4 } from 'uuid';
// Removed: import Redis from 'ioredis';

// Removed Redis client initialization and constants

// Interface for the expected response from the aiservice submission endpoint
interface AIServiceTaskSubmissionResponse {
  task_id: string;
  // Potentially other fields from aiservice, but task_id is key
}

export async function POST(req: NextRequest) {
  const AISERVICE_URL = process.env.AISERVICE_URL || 'http://localhost:8000';
  const correlationId = uuidv4();

  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      console.error('Unauthorized access attempt to /ai/rewrite-content', {
        correlationId,
        reason: 'No session or user ID found',
      });
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userIdFromSession = session.user.id;
    console.info('POST /ai/rewrite-content request received', {
      correlationId,
      userId: userIdFromSession,
    });

    const body = (await req.json()) as RewriteContentRequest;
    const {
      content_blocks_to_rewrite,
      document_metadata,
      user_id: userIdFromRequest,
    } = body;

    if (userIdFromRequest && userIdFromRequest !== userIdFromSession) {
      console.warn('User ID mismatch in /ai/rewrite-content', {
        correlationId,
        sessionUserId: userIdFromSession,
        requestUserId: userIdFromRequest,
        message: 'Using session user ID.',
      });
    }
    const finalUserId = userIdFromSession;

    if (!AISERVICE_URL) {
      console.error('AISERVICE_URL environment variable is not set.', {
        correlationId,
      });
      return NextResponse.json(
        { error: 'AI service configuration error.' },
        { status: 500 },
      );
    }

    if (
      !content_blocks_to_rewrite ||
      !Array.isArray(content_blocks_to_rewrite) ||
      content_blocks_to_rewrite.length === 0
    ) {
      console.warn('Invalid request body for /ai/rewrite-content', {
        correlationId,
        userId: finalUserId,
        error:
          'content_blocks_to_rewrite is required and must be a non-empty array.',
        bodyReceived: body, // Log received body for debugging (could be large)
      });
      return NextResponse.json(
        {
          error:
            'Invalid request body: content_blocks_to_rewrite is required and must be a non-empty array.',
        },
        { status: 400 },
      );
    }

    console.info('Submitting task to aiservice from /ai/rewrite-content', {
      correlationId,
      userId: finalUserId,
      numBlocks: content_blocks_to_rewrite.length,
      aiserviceUrl: `${AISERVICE_URL}/api/v1/ai/submit-rewrite-task`,
    });

    const aiservicePayload = {
      content_blocks_to_rewrite,
      document_metadata,
      user_id: finalUserId,
      correlation_id: correlationId,
    };

    const response = await fetch(
      `${AISERVICE_URL}/api/v1/ai/submit-rewrite-task`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(aiservicePayload),
      },
    );

    if (!response.ok) {
      let errorBody;
      try {
        errorBody = await response.json();
      } catch {
        errorBody = { message: await response.text() };
      }
      console.error('aiservice task submission error', {
        correlationId,
        userId: finalUserId,
        aiserviceStatus: response.status,
        aiserviceErrorBody: errorBody,
      });
      return NextResponse.json(
        {
          error: 'aiservice failed to accept the rewrite task.',
          details:
            errorBody?.message ||
            errorBody?.detail ||
            errorBody ||
            'Unknown error from aiservice submission endpoint',
        },
        { status: response.status },
      );
    }

    const aiserviceResponse =
      (await response.json()) as AIServiceTaskSubmissionResponse;

    if (!aiserviceResponse.task_id) {
      console.error('aiservice did not return a task_id', {
        correlationId,
        userId: finalUserId,
        aiserviceResponse,
      });
      return NextResponse.json(
        { error: 'Failed to get task_id from aiservice.' },
        { status: 500 },
      );
    }

    console.info(
      'Successfully submitted task to aiservice and received task_id',
      {
        correlationId,
        userId: finalUserId,
        taskIdFromAiservice: aiserviceResponse.task_id,
      },
    );
    return NextResponse.json(
      { task_id: aiserviceResponse.task_id },
      { status: 202 },
    );
  } catch (error) {
    console.error('Unhandled error in /ai/rewrite-content API route', {
      correlationId,
      errorDetails:
        error instanceof Error
          ? { message: error.message, stack: error.stack }
          : { message: String(error) },
    });
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    if (error instanceof TypeError && error.message.includes('fetch failed')) {
      return NextResponse.json(
        {
          error: 'Failed to connect to aiservice for task submission.',
          details: errorMessage,
          correlationId,
        },
        { status: 503 },
      );
    }
    return NextResponse.json(
      {
        error: 'Internal server error in Next.js API route.',
        details: errorMessage,
        correlationId,
      },
      { status: 500 },
    );
  }
}
