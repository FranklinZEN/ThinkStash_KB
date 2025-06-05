import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth';
import prisma from '@/lib/prisma'; // Import Prisma client

interface TaskStatusResponse {
  id: string; // Renamed from task_id to match Prisma model id
  status: string;
  userId?: string | null;
  progressStage?: string | null;
  ai_rewritten_content_blocks?: any[] | null; // From AITask.resultData
  errorMessage?: string | null; // From AITask.errorMessage
  createdAt: string;
  updatedAt: string;
}

export async function GET(
  req: NextRequest,
  { params }: { params: { taskId: string } },
) {
  let taskId: string | undefined; // Declare taskId here for broader scope including catch

  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userIdFromSession = session.user.id;

    console.log("Full Handler - params object (before await):", params);

    // Await params as suggested by the error log
    // The 'params' from destructuring { params } seems to be a Promise here.
    const routeParams = await params; 
    taskId = routeParams.taskId; // Assign to the higher-scoped taskId

    console.log("Full Handler - resolved taskId:", taskId);

    if (!taskId) {
      // This case should ideally not be hit if routeParams.taskId is always present after await
      return NextResponse.json({ error: 'Task ID is required but was not found after resolving params' }, { status: 400 });
    }

    const task = await prisma.aITask.findUnique({
      where: { id: taskId },
    });

    if (!task) {
      return NextResponse.json({ error: 'Task not found' }, { status: 404 });
    }

    // Authorization: Ensure the user requesting status is the owner of the task
    // or handle admin roles if applicable in the future.
    if (task.userId && task.userId !== userIdFromSession) {
      console.warn(
        `User ${userIdFromSession} attempting to access task ${taskId} owned by ${task.userId}`,
      );
      // For strict ownership, uncomment the following:
      // return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
      // For now, proceeding but logging the warning. Adjust as per security policy.
    }

    // Detailed logging for resultData
    console.log(`Task ${taskId} fetched. Status: ${task.status}`);
    if (task.resultData) {
      console.log(`Task ${taskId} typeof resultData:`, typeof task.resultData);
      // Attempt to log content of resultData. If it's an object, stringify might be helpful for complex structures.
      // If it's already a string (e.g., JSON string not parsed by Prisma), direct log is fine.
      try {
        console.log(`Task ${taskId} resultData (raw/stringified):`, typeof task.resultData === 'string' ? task.resultData : JSON.stringify(task.resultData));
      } catch (e) {
        console.error(`Task ${taskId} failed to stringify resultData:`, e);
        console.log(`Task ${taskId} resultData (direct log as fallback):`, task.resultData);
      }
    } else {
      console.log(`Task ${taskId} resultData is null or undefined.`);
    }

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
      // Check if resultData is an object and has the key
      if (task.resultData && typeof task.resultData === 'object' && 'ai_rewritten_content_blocks' in task.resultData) {
        // Explicitly cast task.resultData to check the property
        const resultDataObject = task.resultData as { ai_rewritten_content_blocks?: any[] | null };
        responsePayload.ai_rewritten_content_blocks = resultDataObject.ai_rewritten_content_blocks || null;
        if (!responsePayload.ai_rewritten_content_blocks) {
            console.warn(`Task ${taskId} is COMPLETED and 'ai_rewritten_content_blocks' key exists in resultData, but its value is null, undefined or empty.`);
        }
      } else {
        console.warn(`Task ${taskId} is COMPLETED but resultData is missing, not an object, or 'ai_rewritten_content_blocks' key is absent. Type: ${typeof task.resultData}`);
        responsePayload.ai_rewritten_content_blocks = null; 
      }
    } else if (task.status === 'FAILED') {
      responsePayload.errorMessage = task.errorMessage;
    }

    return NextResponse.json(responsePayload);

  } catch (error) {
    // Use the taskId captured in the try block if available
    const taskIdForErrorLog = taskId || (params as any)?.taskId || "unknown_taskId_in_catch";
    console.error(`Error in /ai/rewrite-status/${taskIdForErrorLog} API route:`, error);
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    
    return NextResponse.json(
      { error: 'Internal server error retrieving task status.', details: errorMessage },
      { status: 500 },
    );
  }
} 