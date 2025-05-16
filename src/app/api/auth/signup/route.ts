import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/lib/prisma'; // Reverted to static import
import bcrypt from 'bcryptjs';

export async function POST(req: NextRequest) {
  // Removed extensive environment variable logging block

  try {
    // console.log("!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - Prisma imported successfully !!!!!!!!!!!!!!!!!!"); // Removed

    const body = await req.json();
    const { email, password, name } = body;

    // console.log('Signup request body:', body); // Keep if useful for debugging actual signups

    if (!email || !password) {
      // Kept name as optional based on original logic
      return NextResponse.json(
        { message: 'Email and password are required' },
        { status: 400 },
      );
    }

    const existingUser = await prisma.user.findUnique({
      where: { email },
    });
    // console.log("!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - Checked for existing user !!!!!!!!!!!!!!!!!!"); // Removed

    if (existingUser) {
      return NextResponse.json(
        { message: 'User already exists' },
        { status: 409 },
      );
    }

    const hashedPassword = await bcrypt.hash(password, 10);
    const newUser = await prisma.user.create({
      data: {
        email,
        password: hashedPassword,
        name, // Assuming name can be null/optional if not provided in body
      },
    });
    // console.log("!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - New user created !!!!!!!!!!!!!!!!!!"); // Removed

    const userWithoutPassword = {
      id: newUser.id,
      email: newUser.email,
      name: newUser.name,
    };

    return NextResponse.json(userWithoutPassword, { status: 201 });
  } catch (error) {
    // console.error("!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - CAUGHT ERROR !!!!!!!!!!!!!!!!!!"); // Can be removed
    console.error(
      'Signup Error:', // Keep this essential error log
      error instanceof Error ? error.message : String(error),
      // error // Logging the full error object can be verbose, keep if needed for deep debug
    );
    // If you have error reporting (like Sentry or Google Cloud Error Reporting client) integrated, report here:
    // reportErrorToService(error);

    return NextResponse.json(
      {
        message: 'Internal Server Error', // Generic message to client
        // error: error instanceof Error ? error.message : String(error), // Avoid sending detailed error to client in prod
      },
      { status: 500 },
    );
  }
}
