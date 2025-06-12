import { Prisma } from '@prisma/client';
import prisma from '@/lib/prisma';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { NextResponse } from 'next/server';
import { v4 as uuidv4 } from 'uuid';
import type { RewriteContentRequest } from '@/types/api/ai-service';

export async function POST(req: Request) {
  const correlationId = uuidv4();
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return new NextResponse('Unauthorized', { status: 401 });
    }

    const body = (await req.json()) as RewriteContentRequest;
    const { content_blocks_to_rewrite, document_metadata } = body;

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

    const task = await prisma.task.create({
      data: {
        userId: session.user.id,
        type: 'REWRITE_CONTENT',
        status: 'PENDING',
        payload: {
          correlationId,
          content_blocks_to_rewrite:
            content_blocks_to_rewrite as unknown as Prisma.JsonValue,
          document_metadata:
            document_metadata as unknown as Prisma.JsonValue,
        },
        progressMessage: 'Rewrite task created',
      },
    });

    return NextResponse.json({ taskId: task.id }, { status: 202 });
  } catch (error) {
    console.error('Failed to create rewrite task:', {
      correlationId,
      errorDetails:
        error instanceof Error
          ? { message: error.message, stack: error.stack }
          : { message: String(error) },
    });
    return new NextResponse('Internal Server Error', { status: 500 });
  }
}
