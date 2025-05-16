import { NextRequest, NextResponse } from 'next/server';
// import prisma from '@/lib/prisma'; // We'll try to import it after logging env vars
import bcrypt from 'bcryptjs';

export async function POST(req: NextRequest) {
  // Log environment variables at the VERY beginning of the route handler
  console.log('!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - START !!!!!!!!!!!!!!!!!!');
  console.log(
    '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - DB_USER:',
    process.env.DB_USER,
  );
  console.log(
    '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - DB_PASSWORD:',
    process.env.DB_PASSWORD ? 'Exists' : 'MISSING or empty',
  );
  console.log(
    '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - DB_NAME:',
    process.env.DB_NAME,
  );
  console.log(
    '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - DB_HOST_PATH:',
    process.env.DB_HOST_PATH,
  );
  console.log(
    '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - NEXTAUTH_SECRET:',
    process.env.NEXTAUTH_SECRET ? 'Exists' : 'MISSING or empty',
  );
  console.log(
    '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - DATABASE_URL (initial from env):',
    process.env.DATABASE_URL,
  );
  console.log(
    '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - NODE_ENV:',
    process.env.NODE_ENV,
  );
  console.log(
    '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - END OF ENV VAR LOGS !!!!!!!!!!!!!!!!!!',
  );

  try {
    // Now, try to import/use prisma AFTER logging the env vars
    // This will trigger the code in lib/prisma.ts if it hasn't run already
    const prisma = (await import('@/lib/prisma')).default;
    console.log(
      '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - Prisma imported successfully !!!!!!!!!!!!!!!!!!',
    );

    const body = await req.json();
    const { email, password, name } = body;

    console.log('Signup request body:', body);

    if (!email || !password) {
      return NextResponse.json(
        { message: 'Email and password are required' },
        { status: 400 },
      );
    }

    const existingUser = await prisma.user.findUnique({
      where: { email },
    });
    console.log(
      '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - Checked for existing user !!!!!!!!!!!!!!!!!!',
    );

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
        name,
      },
    });
    console.log(
      '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - New user created !!!!!!!!!!!!!!!!!!',
    );

    const userWithoutPassword = {
      id: newUser.id,
      email: newUser.email,
      name: newUser.name,
    };

    return NextResponse.json(userWithoutPassword, { status: 201 });
  } catch (error) {
    console.error(
      '!!!!!!!!!!!!!!!!! APP ROUTE SIGNUP - CAUGHT ERROR !!!!!!!!!!!!!!!!!!',
    );
    console.error(
      'Signup Error:',
      error instanceof Error ? error.message : String(error),
      error, // Log the full error
    );
    return NextResponse.json(
      {
        message: 'Internal Server Error',
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
}
