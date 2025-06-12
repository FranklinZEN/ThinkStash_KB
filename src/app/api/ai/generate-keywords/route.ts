import { Prisma } from '@prisma/client';
import prisma from '@/lib/prisma';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { NextResponse } from 'next/server';
import type { GenerateKeywordsRequest } from '@/types/api/ai-service';

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user?.id) {
      return new NextResponse('Unauthorized', { status: 401 });
    }

    const body = (await req.json()) as GenerateKeywordsRequest;
    const { content_blocks } = body;

    if (
      !content_blocks ||
      !Array.isArray(content_blocks) ||
      content_blocks.length === 0
    ) {
      return NextResponse.json(
        {
          error:
            'Invalid request body: content_blocks is required and must be a non-empty array.',
        },
        { status: 400 },
      );
    }

    const task = await prisma.task.create({
      data: {
        userId: session.user.id,
        type: 'GENERATE_KEYWORDS',
        status: 'PENDING',
        payload: {
          content_blocks: content_blocks as unknown as Prisma.JsonValue,
        },
        progressMessage: 'Keyword generation task created',
      },
    });

    return NextResponse.json({ taskId: task.id }, { status: 202 });
  } catch (error) {
    console.error('Failed to create keyword generation task:', error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
}
