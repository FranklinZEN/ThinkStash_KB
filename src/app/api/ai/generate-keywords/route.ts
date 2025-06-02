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
      // user_id: userId, // Python KeywordExtractionRequest does not expect user_id
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

    // If response.ok is true, we expect a payload conforming to KeywordExtractionResponse from Python,
    // or at least { suggested_keywords: string[] }.
    const pythonServiceResponse = (await response.json()) as {
      suggested_keywords?: string[];
      error_message?: string;
    }; // Looser type for initial parsing

    // For a successful response (2xx), we prioritize suggested_keywords.
    // Any error message in a 2xx response from Python for keywords is unexpected if it correctly signals errors via HTTP status codes.
    const result: GenerateKeywordsResponse = {
      suggested_keywords: pythonServiceResponse.suggested_keywords || [],
      // error_message: pythonServiceResponse.error_message, // This line is removed. Errors are handled by !response.ok block.
    };

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
