import { NextRequest, NextResponse } from 'next/server';
import type {
  ReconstructAndAnalyzeRequest,
  OrchestrationOutput,
  ContentBlock as AIServiceContentBlock, // Ensure this type matches what aiservice returns (with gcs_url)
  AIServiceReconstructAndAnalyzeRequest, // Import this to use its config type
} from '@/types/api/ai-service';
import { v4 as uuidv4 } from 'uuid'; // For generating job_id
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path if your authOptions are elsewhere
import { Storage } from '@google-cloud/storage'; // Added for GCS Signed URL

// Initialize GCS Storage client
// Make sure your Next.js environment has GOOGLE_APPLICATION_CREDENTIALS set up
// or that the credentials are provided in another secure way.
let storage: Storage;
try {
  storage = new Storage();
} catch (e) {
  console.error(
    'Failed to initialize Google Cloud Storage client. Ensure GOOGLE_APPLICATION_CREDENTIALS are set.',
    e,
  );
  // Depending on your error handling strategy, you might throw here or handle it later
}

// Helper function to generate signed URL
async function generateV4ReadSignedUrl(
  bucketName: string,
  fileName: string,
): Promise<string> {
  if (!storage) {
    throw new Error('GCS Storage client not initialized.');
  }
  // These options will allow temporary read access to the file
  const options = {
    version: 'v4' as const,
    action: 'read' as const,
    expires: Date.now() + 15 * 60 * 1000, // 15 minutes
  };

  try {
    // Get a v4 signed URL for reading the file
    const [url] = await storage
      .bucket(bucketName)
      .file(fileName)
      .getSignedUrl(options);
    return url;
  } catch (error) {
    console.error(
      `Failed to generate signed URL for gs://${bucketName}/${fileName}`,
      error,
    );
    // Depending on how critical this is, you might return a placeholder or throw
    // For now, returning a placeholder that indicates an error.
    return `https://example.com/error-generating-signed-url-for-${fileName.split('/').pop()}`;
  }
}

// const AISERVICE_URL = process.env.AISERVICE_URL || 'http://localhost:8000'; // Moved inside POST

// Define the specific type for the payload to the Python service
interface PythonServicePayload {
  user_id: string;
  job_id: string;
  source_identifier: string;
  source_type: 'url' | 'file' | 'text';
  config?: AIServiceReconstructAndAnalyzeRequest['config'];
}

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
    if (!storage) {
      console.error(
        'GCS Storage client is not initialized. Cannot process image URLs.',
      );
      return NextResponse.json(
        { error: 'Server configuration error related to GCS.' },
        { status: 500 },
      );
    }

    const body = (await req.json()) as ReconstructAndAnalyzeRequest;
    const { source_url, file_id, text_content, config } = body;

    // Validate that at least one and only one source is provided
    const sourcesProvided = [source_url, file_id, text_content].filter(
      Boolean,
    ).length;

    if (sourcesProvided === 0) {
      return NextResponse.json(
        {
          error:
            'Invalid request body: source_url, file_id, or text_content is required.',
        },
        { status: 400 },
      );
    }

    if (sourcesProvided > 1) {
      return NextResponse.json(
        {
          error:
            'Invalid request body: provide only one of source_url, file_id, or text_content.',
        },
        { status: 400 },
      );
    }

    let source_identifier: string;
    let source_type: 'url' | 'file' | 'text';

    if (source_url) {
      source_identifier = source_url;
      source_type = 'url';
    } else if (file_id) {
      source_identifier = file_id;
      source_type = 'file';
    } else if (text_content) {
      source_identifier = text_content; // Or a hash/snippet if preferred for long text
      source_type = 'text';
    } else {
      // This case should ideally be caught by sourcesProvided === 0, but as a safeguard:
      return NextResponse.json(
        {
          error: 'Internal server error: No source identified despite checks.',
        },
        { status: 500 },
      );
    }

    const job_id = uuidv4(); // Generate a unique job ID for this reconstruction task

    console.log(
      `API /ai/reconstruct-and-analyze: Calling Python aiservice for source type: ${source_type}, job_id: ${job_id}`,
    );

    const pythonServicePayload: PythonServicePayload = {
      user_id: userId,
      job_id,
      source_identifier: source_identifier,
      source_type: source_type,
      config: config,
    };

    const response = await fetch(
      `${AISERVICE_URL}/api/v1/ai/reconstruct-and-analyze`,
      {
        // Corrected to match Python service's full path prefix /api/v1/ai
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(pythonServicePayload),
      },
    );

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
        { status: response.status }, // Propagate Python service status if appropriate
      );
    }

    const pythonServiceResponse =
      (await response.json()) as OrchestrationOutput;

    // Process content blocks to generate signed URLs for images
    if (pythonServiceResponse.original_content_blocks && storage) {
      console.log('[NextAPI R&A] Starting GCS signed URL generation for image blocks.');
      for (const block of pythonServiceResponse.original_content_blocks as AIServiceContentBlock[]) {
        if (block.type === 'image') {
          console.log(`[NextAPI R&A] Processing image block ID: ${block.block_id || block.tmp_id || 'N/A'}. Incoming gcs_url: ${block.gcs_url}`);
          if (
            block.gcs_url &&
            block.gcs_url.startsWith('gs://')
          ) {
            console.log(`[NextAPI R&A] gs:// URL found: ${block.gcs_url}. Attempting to generate signed URL.`);
            try {
              const gcsPath = block.gcs_url.substring('gs://'.length);
              const firstSlashIndex = gcsPath.indexOf('/');
              if (firstSlashIndex > 0) {
                const bucketName = gcsPath.substring(0, firstSlashIndex);
                const fileName = gcsPath.substring(firstSlashIndex + 1);

                console.log(
                  `[GCS Signed URL] Generating for: gs://${bucketName}/${fileName}`,
                );
                const signedUrl = await generateV4ReadSignedUrl(
                  bucketName,
                  fileName,
                );
                block.gcs_url = signedUrl; // Replace gs:// URL with signed HTTPS URL
                console.log(
                  `[GCS Signed URL] Successfully generated. New gcs_url (first 100 chars): ${block.gcs_url?.substring(0, 100)}...`,
                );
              } else {
                console.warn(
                  `[GCS Signed URL] Could not parse bucket/file from GCS URL: ${block.gcs_url}`,
                );
              }
            } catch (e) {
              console.error(
                `[GCS Signed URL] Error processing GCS URL ${block.gcs_url}:`,
                e,
              );
              // Decide on fallback: clear gcs_url, set to error, or leave as gs:// ?
              // For now, let's clear it to make the frontend warning accurate if generation fails.
              // block.gcs_url = undefined; // Or some error placeholder if preferred
            }
          } else {
            console.warn(
              `[NextAPI R&A] Image block ID: ${block.block_id || block.tmp_id || 'N/A'} did not have a valid gs:// URL. Current gcs_url: ${block.gcs_url}`,
            );
            // If it's not a gs:// URL, we shouldn't send it to BlockNote if it expects a fetchable HTTPS URL.
            // Consider clearing it if it's not already a valid HTTPS URL from a previous step (unlikely here).
            // if (block.gcs_url && !block.gcs_url.startsWith('https')) {
            //   block.gcs_url = undefined;
            // }
          }
          console.log(`[NextAPI R&A] Final gcs_url for image block ID: ${block.block_id || block.tmp_id || 'N/A'}: ${block.gcs_url}`);
        }
      }
    }

    const result = {
      reconstruction_id: pythonServiceResponse.document_id || job_id,
      status_code: pythonServiceResponse.status_code,
      source_identifier:
        pythonServiceResponse.source_identifier || source_identifier,
      document_metadata: pythonServiceResponse.document_metadata,
      is_long_article: pythonServiceResponse.is_long_article,
      original_content_blocks: pythonServiceResponse.original_content_blocks,
      error_message: pythonServiceResponse.error_message || null,
    };

    if (
      pythonServiceResponse.error_message &&
      pythonServiceResponse.status_code.startsWith('success')
    ) {
      console.warn(
        `Python aiservice (reconstruct) returned an error message in a success payload for job ${job_id}:`,
        pythonServiceResponse.error_message,
      );
    } else if (
      !pythonServiceResponse.status_code.startsWith('success') &&
      pythonServiceResponse.error_message
    ) {
      console.info(
        `Python aiservice (reconstruct) failed for job ${job_id} with status ${pythonServiceResponse.status_code}:`,
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

export async function GET(_request: NextRequest) {
  console.log('!!! /api/ai/reconstruct-and-analyze GET endpoint WAS HIT !!!');
  return NextResponse.json({
    message: 'Hello from GET /api/ai/reconstruct-and-analyze!',
  });
}
