import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '@/lib/auth'; // Adjust path as necessary
import { prisma } from '@/lib/prisma'; // Adjust path as necessary

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);

  if (!session || !session.user?.id) {
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  try {
    const userId = session.user.id;
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        name: true,
        email: true,
        emailVerified: true, // Include if relevant
        image: true,
        createdAt: true,
        updatedAt: true,
        // Explicitly exclude password and other sensitive fields
        // password: false, <-- No need, select includes only specified fields
      },
    });

    if (!user) {
      // This case might indicate an inconsistency if a session exists but the user doesn't
      console.error(`User not found in DB for session user ID: ${userId}`);
      return NextResponse.json({ message: 'User not found' }, { status: 404 });
    }

    return NextResponse.json(user, { status: 200 });

  } catch (error) {
    console.error('Get Profile Error:', error);
    return NextResponse.json({ message: 'Internal Server Error' }, { status: 500 });
  } finally {
    // No need to disconnect if using Prisma singleton pattern typically
    // await prisma.$disconnect();
  }
}

export async function PATCH(req: NextRequest) {
  const session = await getServerSession(authOptions);

  if (!session || !session.user?.id) {
    return NextResponse.json({ message: 'Unauthorized' }, { status: 401 });
  }

  try {
    const userId = session.user.id;
    const body = await req.json();
    const { name } = body;

    // Basic validation
    if (typeof name !== 'string' || name.trim().length === 0) {
      return NextResponse.json({ message: 'Name is required and must be a non-empty string' }, { status: 400 });
    }

    // Update user's name
    const updatedUser = await prisma.user.update({
      where: { id: userId },
      data: {
        name: name.trim(),
      },
      select: { // Return the updated user data (excluding password)
        id: true,
        name: true,
        email: true,
        emailVerified: true,
        image: true,
        createdAt: true,
        updatedAt: true,
      },
    });

    return NextResponse.json(updatedUser, { status: 200 });

  } catch (error) {
    console.error('Update Profile Error:', error);
    // Handle potential Prisma errors, e.g., validation errors
    // You might want more specific error handling here
    return NextResponse.json({ message: 'Internal Server Error' }, { status: 500 });
  } finally {
    // No need to disconnect if using Prisma singleton pattern typically
    // await prisma.$disconnect();
  }
} 