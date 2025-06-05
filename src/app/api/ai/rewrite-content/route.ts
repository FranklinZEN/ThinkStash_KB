import { NextRequest, NextResponse } from 'next/server';
import type {
  RewriteContentRequest,
  // RewriteContentResponse, // This will now be simpler: { task_id: string }
  ContentBlock, // Keep if needed for request body typing, though RewriteContentRequest covers it
} from '@/types/api/ai-service';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth';
// Removed: import { v4 as uuidv4 } from 'uuid';
// Removed: import Redis from 'ioredis';

// Removed Redis client initialization and constants

// Interface for the expected response from the aiservice submission endpoint
interface AIServiceTaskSubmissionResponse {
  task_id: string;
  // Potentially other fields from aiservice, but task_id is key
}

export async function POST(req: NextRequest) {
  const AISERVICE_URL = process.env.AISERVICE_URL || 'http://localhost:8000';
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userIdFromSession = session.user.id;

    const body = (await req.json()) as RewriteContentRequest;
    const {
      content_blocks_to_rewrite,
      document_metadata,
      user_id: userIdFromRequest,
    } = body;

    if (userIdFromRequest && userIdFromRequest !== userIdFromSession) {
      console.warn(
        `User ID mismatch: session ${userIdFromSession}, request ${userIdFromRequest}. Using session user ID.`,
      );
    }
    const finalUserId = userIdFromSession;

    if (!AISERVICE_URL) {
      console.error('AISERVICE_URL environment variable is not set.');
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
      return NextResponse.json(
        {
          error:
            'Invalid request body: content_blocks_to_rewrite is required and must be a non-empty array.',
        },
        { status: 400 },
      );
    }

    console.log(
      `API /ai/rewrite-content by user ${finalUserId}: Submitting task to aiservice with ${content_blocks_to_rewrite.length} blocks.`,
    );

    const aiservicePayload = {
      content_blocks_to_rewrite,
      document_metadata, // This might be optional or handled differently by aiservice now
      user_id: finalUserId,
      // Ensure aiservice's RewriteContentInput model matches this structure or adapt as needed
    };

    const response = await fetch(`${AISERVICE_URL}/api/v1/ai/submit-rewrite-task`, { // New aiservice endpoint
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(aiservicePayload),
    });

    if (!response.ok) {
      let errorBody;
      try {
        errorBody = await response.json();
      } catch (_) {
        errorBody = { message: await response.text() };
      }
      console.error(`aiservice task submission error (${response.status}):`, errorBody);
      return NextResponse.json(
        {
          error: 'aiservice failed to accept the rewrite task.',
          details:
            errorBody?.message ||
            errorBody?.detail || // FastAPI often uses 'detail'
            errorBody ||
            'Unknown error from aiservice submission endpoint',
        },
        { status: response.status },
      );
    }

    const aiserviceResponse = (await response.json()) as AIServiceTaskSubmissionResponse;

    if (!aiserviceResponse.task_id) {
      console.error('aiservice did not return a task_id:', aiserviceResponse);
      return NextResponse.json(
        { error: 'Failed to get task_id from aiservice.' },
        { status: 500 },
      );
    }

    // Return 202 Accepted with the task_id received from aiservice
    return NextResponse.json({ task_id: aiserviceResponse.task_id }, { status: 202 });

  } catch (error) {
    console.error('Error in /ai/rewrite-content API route (aiservice call):', error);
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    if (error instanceof TypeError && error.message.includes('fetch failed')) {
      return NextResponse.json(
        {
          error: 'Failed to connect to aiservice for task submission.',
          details: errorMessage,
        },
        { status: 503 }, // Service Unavailable
      );
    }
    return NextResponse.json(
      {
        error: 'Internal server error in Next.js API route.',
        details: errorMessage,
      },
      { status: 500 },
    );
  }
}
