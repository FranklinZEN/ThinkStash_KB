// Simple example utility function
export const add = (a: number, b: number): number => {
  return a + b;
};

// Example function that might use Prisma (for future integration tests)
// import { prisma } from './prisma';
// export const getUserCount = async (): Promise<number> => {
//   return await prisma.user.count();
// }; 