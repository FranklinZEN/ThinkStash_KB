import { NextRequest, NextResponse } from 'next/server';
import type {
  ReconstructAndAnalyzeRequest,
  OrchestrationOutput,
} from '@/types/api/ai-service';
import { v4 as uuidv4 } from 'uuid'; // For generating job_id
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

    if (!AISERVICE_URL) {
      console.error('AISERVICE_URL environment variable is not set.');
      return NextResponse.json(
        { error: 'AI service configuration error.' },
        { status: 500 },
      );
    }

    const body = (await req.json()) as ReconstructAndAnalyzeRequest;
    const { source_url, file_id } = body;

    if (!source_url && !file_id) {
      return NextResponse.json(
        { error: 'Invalid request body: source_url or file_id is required.' },
        { status: 400 },
      );
    }
    if (source_url && file_id) {
      return NextResponse.json(
        {
          error:
            'Invalid request body: provide either source_url or file_id, not both.',
        },
        { status: 400 },
      );
    }

    const source_identifier = source_url || file_id!;
    // Determine source_type based on input. More sophisticated logic might be needed for file_id.
    const source_type = source_url ? 'url' : 'file'; // This is a simplification
    const job_id = uuidv4(); // Generate a unique job ID for this reconstruction task

    console.log(
      `API /ai/reconstruct-and-analyze: Calling Python aiservice for source: ${source_identifier}, job_id: ${job_id}`,
    );

    const pythonServicePayload = {
      source_identifier,
      source_type,
      user_id: userId, // Use actual userId from session
      job_id,
      // processing_level: "full_content", // Default in Python OrchestrationInput
      // output_format_options: {}, // Default in Python OrchestrationInput
    };

    const response = await fetch(`${AISERVICE_URL}/reconstruct-and-analyze`, {
      // Ensure this matches Python API endpoint
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
          error: 'Python aiservice failed to reconstruct and analyze content.',
          details:
            errorBody?.message ||
            errorBody ||
            'Unknown error from Python service',
          reconstruction_id: job_id, // Return job_id even on failure for tracking
        },
        { status: response.status },
      );
    }

    // Expecting the Python service to return the OrchestrationOutput structure
    const pythonServiceResponse =
      (await response.json()) as OrchestrationOutput;

    // Map the Python OrchestrationOutput to the slightly different structure if needed,
    // or ensure OrchestrationOutput in ai-service-types.ts matches exactly what Python returns
    // and what this Next.js API should return.
    // For now, assuming OrchestrationOutput type is suitable directly.
    // The V2.6 plan mentioned `reconstruction_id` as a top-level field in Next.js response.
    // OrchestrationOutput has `document_id` which should be our job_id.

    const result = {
      ...pythonServiceResponse,
      reconstruction_id: pythonServiceResponse.document_id || job_id, // Ensure reconstruction_id is present
    };

    if (pythonServiceResponse.error_message) {
      console.warn(
        `Python aiservice (reconstruct) returned an error in the success payload for job ${job_id}:`,
        pythonServiceResponse.error_message,
      );
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error('Error in /ai/reconstruct-and-analyze API route:', error);
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
