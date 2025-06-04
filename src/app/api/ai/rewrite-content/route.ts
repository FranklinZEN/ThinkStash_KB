import { NextRequest, NextResponse } from 'next/server';
import type {
  RewriteContentRequest,
  RewriteContentResponse,
  ContentBlock,
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
    const userIdFromSession = session.user.id;

    const body = (await req.json()) as RewriteContentRequest;
    // Ensure user_id in payload matches session user_id if provided, or use session user_id
    const {
      content_blocks_to_rewrite,
      document_metadata,
      user_id: userIdFromRequest,
    } = body;

    if (userIdFromRequest && userIdFromRequest !== userIdFromSession) {
      console.warn(
        `User ID mismatch: session ${userIdFromSession}, request ${userIdFromRequest}. Using session user ID.`,
      );
      // Optionally return 403 Forbidden if user_id in request is for someone else
      // return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }
    const finalUserId = userIdFromSession; // Always prioritize userId from session

    if (!AISERVICE_URL) {
      console.error('AISERVICE_URL environment variable is not set.');
      return NextResponse.json(
        { error: 'AI service configuration error.' },
        { status: 500 },
      );
    }

    if (
      !content_blocks_to_rewrite ||
      !Array.isArray(content_blocks_to_rewrite)
    ) {
      return NextResponse.json(
        {
          error:
            'Invalid request body: content_blocks_to_rewrite is required and must be an array.',
        },
        { status: 400 },
      );
    }

    console.log(
      `API /ai/rewrite-content by user ${finalUserId}: Calling Python aiservice with ${content_blocks_to_rewrite.length} blocks.`,
    );

    const pythonServicePayload = {
      content_blocks_to_rewrite,
      document_metadata,
      user_id: finalUserId, // Ensure this is the authenticated user's ID
    };

    const response = await fetch(`${AISERVICE_URL}/api/v1/ai/rewrite-content`, {
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
          error: 'Python aiservice failed to rewrite content.',
          details:
            errorBody?.message ||
            errorBody ||
            'Unknown error from Python service',
        },
        { status: response.status },
      );
    }

    // Define a type for the expected broader output from the Python service
    // This includes fields we might not directly expose via this Next.js API route,
    // but are present in the Python 'RewriteContentOutput' model.
    interface PythonServiceRewriteOutput {
      rewritten_document_id?: string | null;
      ai_rewritten_content_blocks: ContentBlock[]; // Changed from any[] to ContentBlock[]
      status_code?: string;
      error_message?: string | null;
      processing_time_ms?: number | null;
      usage_metrics?: Record<string, unknown>; // Changed from Record<string, any> to Record<string, unknown>
      trace_id?: string; // Example of an extra field
    }

    const pythonServiceResponse =
      (await response.json()) as PythonServiceRewriteOutput;

    if (
      pythonServiceResponse.error_message &&
      pythonServiceResponse.status_code &&
      pythonServiceResponse.status_code.toLowerCase().includes('success')
    ) {
      console.warn(
        'Python aiservice (rewrite) returned an error message in an apparent success payload:',
        pythonServiceResponse.error_message,
      );
    } else if (pythonServiceResponse.error_message) {
      console.info(
        `Python aiservice (rewrite) returned an error message: ${pythonServiceResponse.error_message} with status: ${pythonServiceResponse.status_code}`,
      );
    }

    // Construct the response for the Next.js client, adhering to RewriteContentResponse type
    const nextJsResponsePayload: RewriteContentResponse = {
      rewritten_document_id: pythonServiceResponse.rewritten_document_id,
      ai_rewritten_content_blocks:
        pythonServiceResponse.ai_rewritten_content_blocks,
      status_code: pythonServiceResponse.status_code,
      error_message: pythonServiceResponse.error_message,
      processing_time_ms: pythonServiceResponse.processing_time_ms,
    };

    return NextResponse.json(nextJsResponsePayload);
  } catch (error) {
    console.error('Error in /ai/rewrite-content API route:', error);
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
