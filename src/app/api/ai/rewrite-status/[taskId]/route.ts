import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth';
import prisma from '@/lib/prisma'; // Import Prisma client
import { ContentBlock } from '@/types/api/ai-service';

interface TaskStatusResponse {
  id: string; // Renamed from task_id to match Prisma model id
  status: string;
  userId?: string | null;
  progressStage?: string | null;
  ai_rewritten_content_blocks?: ContentBlock[] | null; // From AITask.resultData
  errorMessage?: string | null; // From AITask.errorMessage
  createdAt: string;
  updatedAt: string;
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ taskId: string }> },
): Promise<NextResponse> {
  let resolvedTaskId: string | undefined;

  try {
    const { taskId } = await params;
    resolvedTaskId = taskId;

    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      // No taskId available yet for this specific log, but context is clear
      console.error('Unauthorized access attempt to /ai/rewrite-status', {
        reason: 'No session or user ID found',
        requestPath: req.nextUrl.pathname,
      });
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userIdFromSession = session.user.id;

    console.info('GET /ai/rewrite-status/[taskId] request received', {
      taskId: resolvedTaskId,
      userId: userIdFromSession,
    });

    if (!resolvedTaskId) {
      console.error('Task ID missing in /ai/rewrite-status request params', {
        userId: userIdFromSession,
        paramsReceived: params,
      });
      return NextResponse.json(
        { error: 'Task ID is required' },
        { status: 400 },
      );
    }

    const task = await prisma.aITask.findUnique({
      where: { id: resolvedTaskId },
    });

    if (!task) {
      console.warn('Task not found in /ai/rewrite-status', {
        taskId: resolvedTaskId,
        userId: userIdFromSession,
      });
      return NextResponse.json({ error: 'Task not found' }, { status: 404 });
    }

    if (task.userId && task.userId !== userIdFromSession) {
      console.warn('Forbidden access attempt to task in /ai/rewrite-status', {
        taskId: resolvedTaskId,
        requestingUserId: userIdFromSession,
        taskOwnerId: task.userId,
      });
      // return NextResponse.json({ error: 'Forbidden' }, { status: 403 }); // Uncomment for strict check
    }

    console.info('Task fetched successfully', {
      taskId: resolvedTaskId,
      status: task.status,
      userId: task.userId,
      progressStage: task.progressStage,
      hasResultData: task.resultData != null,
    });

    // Removed verbose logging of raw resultData to keep logs cleaner by default
    // Can be added back temporarily for specific debugging if needed

    const responsePayload: TaskStatusResponse = {
      id: task.id,
      status: task.status,
      userId: task.userId,
      progressStage: task.progressStage,
      createdAt: task.createdAt.toISOString(),
      updatedAt: task.updatedAt.toISOString(),
      ai_rewritten_content_blocks: null,
      errorMessage: null,
    };

    if (task.status === 'COMPLETED') {
      if (task.resultData) {
        try {
          // The resultData is stored as a JSON string, so we need to parse it.
          const resultDataObject = JSON.parse(task.resultData as string);

          if (
            resultDataObject &&
            resultDataObject.ai_rewritten_content_blocks
          ) {
            responsePayload.ai_rewritten_content_blocks =
              resultDataObject.ai_rewritten_content_blocks;
          } else {
            console.warn(
              "Task COMPLETED and resultData parsed, but 'ai_rewritten_content_blocks' key is missing or null.",
              {
                taskId: resolvedTaskId,
              },
            );
          }
        } catch (parseError) {
          console.error('Task COMPLETED but failed to parse resultData JSON.', {
            taskId: resolvedTaskId,
            error:
              parseError instanceof Error
                ? parseError.message
                : String(parseError),
            resultDataPreview: (task.resultData as string).substring(0, 100),
          });
        }
      } else {
        console.warn('Task COMPLETED but resultData is null or empty.', {
          taskId: resolvedTaskId,
        });
      }
    } else if (task.status === 'FAILED') {
      responsePayload.errorMessage = task.errorMessage;
      console.info('Task status is FAILED, including error message.', {
        taskId: resolvedTaskId,
        errorMessage: task.errorMessage,
      });
    }

    console.info('Returning task status successfully.', {
      taskId: resolvedTaskId,
      status: responsePayload.status,
    });
    return NextResponse.json(responsePayload);
  } catch (error) {
    console.error('Unhandled error in /ai/rewrite-status/[taskId] API route', {
      taskId: resolvedTaskId || 'unknown_taskId_in_catch',
      errorDetails:
        error instanceof Error
          ? { message: error.message, stack: error.stack }
          : { message: String(error) },
    });
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';

    return NextResponse.json(
      {
        error: 'Internal server error retrieving task status.',
        details: errorMessage,
      },
      { status: 500 },
    );
  }
}
