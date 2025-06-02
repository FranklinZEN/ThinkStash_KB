import { NextRequest, NextResponse } from 'next/server';
import type {
  GenerateKeywordsRequest,
  GenerateKeywordsResponse,
} from '@/types/api/ai-service';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path if your authOptions are elsewhere

// const AISERVICE_URL = process.env.AISERVICE_URL || 'http://localhost:8000'; // Moved inside POST

export async function POST(req: NextRequest) {
  // Read AISERVICE_URL inside the handler to ensure it picks up test-specific env vars
  const AISERVICE_URL = process.env.AISERVICE_URL || 'http://localhost:8000';
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userId = session.user.id;

    const body = (await req.json()) as GenerateKeywordsRequest;
    const { content_blocks } = body;

    if (!AISERVICE_URL) {
      console.error('AISERVICE_URL environment variable is not set.');
      return NextResponse.json(
        { error: 'AI service configuration error.' },
        { status: 500 },
      );
    }

    if (!content_blocks || !Array.isArray(content_blocks)) {
      return NextResponse.json(
        {
          error:
            'Invalid request body: content_blocks is required and must be an array.',
        },
        { status: 400 },
      );
    }

    console.log(
      `API /ai/generate-keywords by user ${userId}: Calling Python aiservice with ${content_blocks.length} blocks.`,
    );

    const pythonServicePayload = {
      content_blocks,
      user_id: userId, // Pass userId to the Python service (optional for service, good for logging)
    };

    const response = await fetch(`${AISERVICE_URL}/generate-keywords`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(pythonServicePayload),
    });

    if (!response.ok) {
      let errorBody;
      try {
        errorBody = await response.json();
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
      } catch (_) {
        errorBody = { message: await response.text() };
      }
      console.error(`Python aiservice error (${response.status}):`, errorBody);
      return NextResponse.json(
        {
          error: 'Python aiservice failed to generate keywords.',
          details:
            errorBody?.message ||
            errorBody ||
            'Unknown error from Python service',
        },
        { status: response.status },
      );
    }

    const pythonServiceResponse = await response.json();
    // Assuming the Python service returns a JSON object with a `suggested_keywords` field
    // and potentially an `error_message` field, conforming to our GenerateKeywordsResponse.
    const result: GenerateKeywordsResponse = {
      suggested_keywords: pythonServiceResponse.suggested_keywords || [], // Default to empty array if undefined
      error_message: pythonServiceResponse.error_message,
    };

    if (result.error_message) {
      console.warn(
        'Python aiservice (keywords) returned an error in the success payload:',
        result.error_message,
      );
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error('Error in /ai/generate-keywords API route:', error);
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    if (error instanceof TypeError && error.message.includes('fetch failed')) {
      return NextResponse.json(
        {
          error: 'Failed to connect to Python aiservice.',
          details: errorMessage,
        },
        { status: 503 },
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
