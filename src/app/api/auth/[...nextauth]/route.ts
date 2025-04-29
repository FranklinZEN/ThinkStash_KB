import NextAuth from "next-auth";
import { authOptions } from "@/lib/auth"; // Import the configured options

// Initialize NextAuth.js with the options
const handler = NextAuth(authOptions);

// Export the handler for GET and POST requests as required by NextAuth.js
export { handler as GET, handler as POST }; 