// import { PrismaAdapter } from "@next-auth/prisma-adapter";
import { NextAuthOptions, User, Account, Profile, Session } from 'next-auth';
import type { AdapterUser } from 'next-auth/adapters'; // Corrected import for AdapterUser
import CredentialsProvider from 'next-auth/providers/credentials';
import prisma from './prisma'; // Use default import
// import { PrismaClient } from "@prisma/client"; // Remove direct import
import bcrypt from 'bcryptjs';
import { JWT } from 'next-auth/jwt';

// Remove local PrismaClient instantiation
// const prisma = new PrismaClient();

// Define custom types to include accessToken
interface ExtendedUser extends User {
  accessToken?: string;
  // id: string; // User['id'] is already string
}

interface ExtendedToken extends JWT {
  accessToken?: string;
  id: string; // Our required user ID, distinct from JWT's sub if needed, but usually mapped from sub or user.id
  // We could also choose to use 'sub' directly if we ensure it's always populated.
  // For clarity, keeping 'id'.
}

interface ExtendedSession extends Session {
  accessToken?: string;
  user: {
    id: string;
    name?: string | null;
    email?: string | null;
    image?: string | null;
  };
}

export const authOptions: NextAuthOptions = {
  // Temporarily comment out the adapter to test JWT-only sessions
  // adapter: PrismaAdapter(prisma),
  providers: [
    CredentialsProvider({
      // The name to display on the sign in form (e.g. 'Sign in with...')
      name: 'Credentials',
      // The credentials is used to generate a suitable form on the sign in page.
      credentials: {
        email: {
          label: 'Email',
          type: 'email',
          placeholder: 'jsmith@example.com',
        },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials, _req) {
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
          const isValid = await bcrypt.compare(
            credentials.password,
            user.password,
          );

          if (isValid) {
            console.log('Password valid for user:', user.email);
            // Return essential user info (IMPORTANT: DO NOT return password)
            // Also returning accessToken if available from provider (though for credentials, it's usually set in jwt callback)
            return {
              id: user.id,
              name: user.name,
              email: user.email,
              image: user.image, // Include image if needed
              // accessToken: user.accessToken // Assuming you might add it to your user model later or from OAuth
            } as ExtendedUser;
          } else {
            console.log('Password invalid for user:', user.email);
            return null; // Password incorrect
          }
        } catch (error) {
          console.error('Authorize error:', error);
          return null; // Indicate failure
        }
      },
    }),
  ],
  session: {
    // Keep JWT strategy, required when adapter is disabled
    strategy: 'jwt', // Use JWT strategy
  },
  callbacks: {
    async jwt({
      token,
      user,
      account,
      _profile,
      _isNewUser,
    }: {
      token: JWT;
      user?: User | ExtendedUser;
      account?: Account | null;
      _profile?: Profile;
      _isNewUser?: boolean;
    }): Promise<ExtendedToken> {
      const newToken: Omit<ExtendedToken, 'id'> & {
        id?: string;
        accessToken?: string;
      } = {
        ...token,
      };

      if (user) {
        newToken.id = user.id;
      }

      if (account) {
        newToken.accessToken = account.access_token;
      }

      if (!newToken.id && token.sub) {
        newToken.id = token.sub;
      }

      if (typeof newToken.id !== 'string') {
        throw new Error(
          'User ID (id) is missing or not a string in JWT token processing.',
        );
      }

      return newToken as ExtendedToken;
    },
    // Session callback receives the token from JWT callback. Expect standard JWT type, then cast.
    async session({
      session,
      token,
      user,
    }: {
      session: Session;
      token: JWT;
      user: User | ExtendedUser | AdapterUser;
    }): Promise<ExtendedSession> {
      // The `token` here is the one processed by our `jwt` callback.
      // We expect it to conform to `ExtendedToken`.
      const _unusedUser = user; // Rename to _unusedUser if not used further to satisfy ESLint
      const extendedToken = token as ExtendedToken;

      // Start building the new session, typed as our ExtendedSession.
      // Explicitly cast the incoming session to ExtendedSession if needed, or construct new.
      const newSession = { ...session } as ExtendedSession;

      // Ensure user object exists on the session to avoid runtime errors.
      // The default Session type already has a user object { id: string; name?: string; ... }
      // So, session.user should exist.
      if (!newSession.user) {
        // This case should ideally not happen with default session structure
        // Initialize it if somehow missing, matching ExtendedSession structure
        newSession.user = { id: '' }; // id is required
      }

      // Populate ExtendedSession from ExtendedToken
      newSession.user.id = extendedToken.id; // extendedToken.id is string
      if (extendedToken.accessToken) {
        newSession.accessToken = extendedToken.accessToken;
      }

      // Populate other user details from the token if they exist
      // (name, email, image/picture are standard JWT claims often included by NextAuth)
      if (extendedToken.name) newSession.user.name = extendedToken.name;
      if (extendedToken.email) newSession.user.email = extendedToken.email;
      // NextAuth often puts profile image URL in `picture` claim in JWT, `image` in session.user
      if (extendedToken.picture) newSession.user.image = extendedToken.picture;
      else if (extendedToken.image)
        newSession.user.image = extendedToken.image as
          | string
          | null
          | undefined; // if our token uses 'image'

      return newSession;
    },
  },
  // Ensure NEXTAUTH_SECRET is set in .env
  secret: process.env.NEXTAUTH_SECRET,
  // Add other configurations like pages if needed
  // pages: {
  //   signIn: '/auth/signin',
  // }
};
