// import { PrismaAdapter } from "@next-auth/prisma-adapter";
import { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import { prisma } from "./prisma"; // Restore singleton import
// import { PrismaClient } from "@prisma/client"; // Remove direct import
import bcrypt from 'bcryptjs';

// Remove local PrismaClient instantiation
// const prisma = new PrismaClient(); 

export const authOptions: NextAuthOptions = {
  // Temporarily comment out the adapter to test JWT-only sessions
  // adapter: PrismaAdapter(prisma), 
  providers: [
    CredentialsProvider({
      // The name to display on the sign in form (e.g. 'Sign in with...')
      name: "Credentials",
      // The credentials is used to generate a suitable form on the sign in page.
      credentials: {
        email: { label: "Email", type: "email", placeholder: "jsmith@example.com" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials, req) {
        // Validate input
        if (!credentials?.email || !credentials?.password) {
          console.log('Credentials missing');
          return null;
        }

        try {
          // Use the singleton prisma instance here
          const user = await prisma.user.findUnique({
            where: { email: credentials.email },
          });

          if (!user) {
            console.log('No user found for email:', credentials.email);
            return null; // User not found
          }

          // Check password
          const isValid = await bcrypt.compare(credentials.password, user.password);

          if (isValid) {
            console.log('Password valid for user:', user.email);
            // Return essential user info (IMPORTANT: DO NOT return password)
            return {
              id: user.id,
              name: user.name,
              email: user.email,
              image: user.image, // Include image if needed
            };
          } else {
            console.log('Password invalid for user:', user.email);
            return null; // Password incorrect
          }
        } catch (error) {
          console.error('Authorize error:', error);
          return null; // Indicate failure
        }
      }
    })
  ],
  session: {
    // Keep JWT strategy, required when adapter is disabled
    strategy: "jwt", // Use JWT strategy
  },
  callbacks: {
    // Callbacks are still used for JWT
    async jwt({ token, user }) {
      // The 'user' object is passed on initial sign-in
      if (user) {
        token.id = user.id;
        token.name = user.name;
        token.email = user.email;
        // Include other fields from user if needed
      }
      return token;
    },
    async session({ session, token }) {
      // Add the user id, name, email from the token to the session object
      if (token && session.user) {
        session.user.id = token.id as string;
        session.user.name = token.name as string | null | undefined;
        session.user.email = token.email as string | null | undefined;
        // Add other properties from token if needed
      }
      return session;
    },
  },
  // Ensure NEXTAUTH_SECRET is set in .env
  secret: process.env.NEXTAUTH_SECRET,
  // Add other configurations like pages if needed
  // pages: {
  //   signIn: '/auth/signin',
  // }
}; 