import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma'; // Import the singleton instance

export async function GET(req: NextRequest) {
  try {
    console.log('Attempting DB connection test...');
    // Perform a simple query - count users
    const userCount = await prisma.user.count();
    console.log(`DB connection test successful. User count: ${userCount}`);
    return NextResponse.json({ success: true, userCount: userCount }, { status: 200 });
  } catch (error: any) {
    console.error('DB Connection Test Error:', error);
    // Return the actual error message for better debugging
    return NextResponse.json(
      { success: false, error: error.message, stack: error.stack }, 
      { status: 500 }
    );
  } 
  // No finally/disconnect needed for singleton
} 