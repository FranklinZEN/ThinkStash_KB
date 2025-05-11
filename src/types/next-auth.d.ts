import 'next-auth';
import 'next-auth/jwt';

declare module 'next-auth' {
  /**
   * Extends the built-in session types to include the properties we added.
   */
  interface Session {
    accessToken?: string; // Add your custom property
    user: {
      id: string; // Ensure user.id is a string and not optional
    } & Omit<DefaultSession['user'], 'id'>; // Combine with default user properties, omitting original id to avoid conflict if its type differs
  }

  /**
   * Extends the built-in user types.
   * This is used if you are adding custom properties to the User object returned by the authorize callback.
   */
  // interface User {
  //   id: string;
  //   // Add other custom properties if needed
  // }
}

declare module 'next-auth/jwt' {
  /**
   * Extends the built-in JWT types.
   */
  interface JWT {
    accessToken?: string; // Add your custom property
    id: string; // Add our id property
    // We could also use 'sub' directly if we ensure it's always populated by our JWT callback and it represents the user ID.
    // For consistency with Session.user.id, we add 'id'.
  }
}
