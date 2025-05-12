import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/lib/prisma';

export async function GET(_req: NextRequest) {
  try {
    console.log('Attempting DB connection test...');
    // Perform a simple query - count users
    const userCount = await prisma.user.count();
    console.log(`DB connection test successful. User count: ${userCount}`);
    return NextResponse.json(
      { success: true, userCount: userCount },
      { status: 200 },
    );
  } catch (error: unknown) {
    console.error('DB Connection Test Error:', error);
    let message = 'An unknown error occurred during DB test.';
    let stack: string | undefined = undefined;
    if (error instanceof Error) {
      message = error.message;
      stack = error.stack;
    }
    return NextResponse.json(
      { success: false, error: message, stack: stack },
      { status: 500 },
    );
  }
  // No finally/disconnect needed for singleton
}
