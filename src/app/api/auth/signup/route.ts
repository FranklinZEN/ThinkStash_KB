import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma'; // Import singleton instance
import bcrypt from 'bcryptjs';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { email, password, name } = body;

    // Log the incoming request body for debugging
    console.log('Signup request body:', body);

    // Basic validation
    if (!email || !password) {
      return NextResponse.json({ message: 'Email and password are required' }, { status: 400 });
    }

    // Check if user already exists
    const existingUser = await prisma.user.findUnique({
      where: { email },
    });

    if (existingUser) {
      return NextResponse.json({ message: 'User already exists' }, { status: 409 });
    }

    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10); // 10 is the salt rounds

    // Create user
    const newUser = await prisma.user.create({
      data: {
        email,
        password: hashedPassword,
        name, // Name is optional, Prisma handles null if not provided
      },
    });

    // Exclude password from the response
    const { password: _, ...userWithoutPassword } = newUser;

    return NextResponse.json(userWithoutPassword, { status: 201 });

  } catch (error) {
    // Log the error with more detail
    console.error('Signup Error:', error instanceof Error ? error.message : error);
    return NextResponse.json({ message: 'Internal Server Error', error: error instanceof Error ? error.message : error }, { status: 500 });
  }
} 