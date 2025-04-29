// src/lib/sessionUtils.ts
import { authOptions } from './auth'; // Adjust path if needed
import { getServerSession } from 'next-auth/next';

export async function getCurrentUserId(): Promise<string | null> {
  const session = await getServerSession(authOptions);
  // Adjust the path to user ID as per your session structure
  return session?.user?.id ?? null;
}