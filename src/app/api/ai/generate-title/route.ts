import { NextRequest, NextResponse } from 'next/server';
import type {
  GenerateTitleRequest,
  GenerateTitleResponse,
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

    const body = (await req.json()) as GenerateTitleRequest;
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
      `API /ai/generate-title by user ${userId}: Calling Python aiservice with ${content_blocks.length} blocks.`,
    );

    const pythonServicePayload = {
      content_blocks,
      // user_id: userId, // Python TitleGenerationRequest does not expect user_id
    };

    const response = await fetch(`${AISERVICE_URL}/api/v1/ai/generate-title`, {
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
        errorBody = { message: await response.text() }; // Fallback if error response is not JSON
      }
      console.error(`Python aiservice error (${response.status}):`, errorBody);
      return NextResponse.json(
        {
          error: 'Python aiservice failed to generate title.',
          details:
            errorBody?.message ||
            errorBody ||
            'Unknown error from Python service',
        },
        { status: response.status },
      );
    }

    // The Python service for title generation (GeneralPurposeTitleGenerationCrew)
    // returns a JSON object like: { "suggested_title": "Actual title or error message" }
    interface PythonTitleServiceResponse {
      suggested_title: string;
      // It does not explicitly send a separate error_message field.
      // Errors are embedded in the suggested_title string.
    }

    const pythonServiceResponse =
      (await response.json()) as PythonTitleServiceResponse;

    let final_suggested_title: string = '';
    let final_error_message: string | undefined = undefined;

    if (
      pythonServiceResponse.suggested_title &&
      pythonServiceResponse.suggested_title.startsWith('Error:')
    ) {
      final_error_message = pythonServiceResponse.suggested_title;
      console.warn(
        `Python aiservice (generate-title) indicated an error: ${final_error_message}`,
      );
    } else if (pythonServiceResponse.suggested_title) {
      final_suggested_title = pythonServiceResponse.suggested_title;
    } else {
      // Should not happen if Python service always returns the suggested_title field
      final_error_message =
        'Python service returned an unexpected response format for title generation.';
      console.error(final_error_message, pythonServiceResponse);
    }

    const result: GenerateTitleResponse = {
      suggested_title: final_suggested_title,
      error_message: final_error_message,
      // alternatives: undefined, // Not provided by this crew
    };

    // No need for the specific error check here anymore as it's handled above
    // if (result.error_message) {
    //   console.warn(
    //     'Python aiservice returned an error in the success payload:',
    //     result.error_message,
    //   );
    // }

    return NextResponse.json(result);
  } catch (error) {
    console.error('Error in /ai/generate-title API route:', error);
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    // Distinguish between network/fetch errors and other errors
    if (error instanceof TypeError) {
      // Catch any TypeError as a potential network/fetch issue
      return NextResponse.json(
        {
          error: 'Failed to connect to Python aiservice.',
          details: errorMessage,
        },
        { status: 503 },
      ); // Service Unavailable
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
