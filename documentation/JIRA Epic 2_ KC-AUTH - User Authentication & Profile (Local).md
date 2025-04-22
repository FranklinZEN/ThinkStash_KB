## **JIRA Epic: KC-AUTH \- User Authentication & Profile (Stage 1\)**

**Rationale:** Provide basic, secure local user authentication and profile management.

Ticket ID: KC-AUTH-UX-1  
Title: Design Authentication User Flow & Components (Local Focus)  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-1, FR-AUTH-2, FR-AUTH-6  
Team: UX  
Dependencies (Functional): Decision on UI Lib (KC-SETUP-3 \- Chakra UI primary)  
UX/UI Design Link:   
Login:[https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=3-86](https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=3-86)  
Registration:[https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=0-1\&p=f\&t=oifw4pbxybZKxbMa-0](https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=0-1&p=f&t=oifw4pbxybZKxbMa-0)  
Profile:[https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=19-69\&p=f\&t=oifw4pbxybZKxbMa-0](https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=19-69&p=f&t=oifw4pbxybZKxbMa-0)

Description (Functional): Design the user experience for registering and logging in with email/password for the local application. Design the basic profile page where users can see their details and update their name.  
Acceptance Criteria (Functional):

* Clear wireframes exist for Registration, Login, and Profile pages.  
* High-fidelity mockups show visual design using Chakra UI components, including all states (inputs, buttons, errors, success).  
* Error messages and interaction flows are clearly defined.  
* Designs are responsive.  
  Technical Approach / Implementation Notes:  
* Provide specific component states needed (e.g., Button isLoading, Input isInvalid).  
* Define exact validation messages texts (e.g., "Email is required", "Password must meet complexity requirements"). *(Note: Ensure password validation aligns with PRD Requirement FR-AUTH-4: Minimum 6 characters, 1 upper, 1 lower, 1 number, 1 special character)*.  
* Ensure design accounts for accessibility (Chakra helps, but verify color contrast, focus states, labels).  
* Specify layout using Chakra components (e.g., VStack, FormControl).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved: N/A (Design artifact)  
  Testing Considerations (Technical): Usability testing on prototypes. Accessibility check.  
  Dependencies (Technical): KC-SETUP-3 (Chakra UI chosen)

Ticket ID: KC-3.1  
Title: Define User Schema in Prisma  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-1, FR-AUTH-6  
Team: BE  
Dependencies (Functional): KC-SETUP-2  
UX/UI Design Link: N/A  
Description (Functional): Define the database structure needed to store user account information, including their name, email, and securely stored password.  
Acceptance Criteria (Functional):

* The database can store unique users based on email.  
* User's name and hashed password can be stored.  
* Timestamps for creation/update are recorded.  
  Technical Approach / Implementation Notes:  
* In prisma/schema.prisma, define:  
  model User {  
    id        String   @id @default(cuid())  
    name      String?  
    email     String   @unique  
    password  String  
    createdAt DateTime @default(now())  
    updatedAt DateTime @updatedAt

    // Stage 1 Relations:  
    cards     Card\[\]  
    folders   Folder\[\]

    // Stage 2 Relations (Optional \- for NextAuth Prisma Adapter if used later):  
    // accounts  Account\[\]  
    // sessions  Session\[\]  
  }

  // Stage 2 Models for NextAuth Adapter (if chosen over JWT):  
  // model Account { ... }  
  // model Session { ... }  
  // model VerificationToken { ... }

* Run npx prisma migrate dev \--name add-user-model.  
* Run npx prisma generate.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): Creates User table/model.  
  Key Functions/Modules Involved:  
* prisma/schema.prisma  
* prisma/migrations/...  
  Testing Considerations (Technical): Verify migration applies cleanly. Check unique constraint on email.  
  Dependencies (Technical): KC-SETUP-2

Ticket ID: KC-2  
Title: Implement Password Hashing using bcryptjs  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-4  
Team: BE  
Dependencies (Functional): KC-SETUP-2  
UX/UI Design Link: N/A  
Description (Functional): Ensure user passwords are never stored directly, but are securely hashed using a standard algorithm before saving, and that logins correctly compare provided passwords against the stored hashes.  
Acceptance Criteria (Functional):

* Passwords entered during registration are not stored in plain text.  
* Login works only when the correct password is provided.  
  Technical Approach / Implementation Notes:  
* Create src/lib/security.ts.  
* Implement:  
  import bcrypt from 'bcryptjs';

  export async function hashPassword(password: string): Promise\<string\> {  
    // Salt rounds factor (10-12 is generally recommended)  
    return bcrypt.hash(password, 10);  
  }

  export async function comparePassword(plain: string, hashed: string): Promise\<boolean\> {  
    return bcrypt.compare(plain, hashed);  
  }

* Install types: npm install \-D @types/bcryptjs.  
* Use these functions in KC-5 (registration) and KC-1.2 (login).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A (Relies on User.password field from KC-3.1)  
  Key Functions/Modules Involved:  
* lib/security.ts  
* Registration API handler (KC-5)  
* NextAuth authorize function (KC-1.2)  
  Testing Considerations (Technical): Unit test hashPassword and comparePassword utility functions.  
  Dependencies (Technical): KC-SETUP-2

Ticket ID: KC-1.1  
Title: Configure NextAuth.js Core Setup (Local JWT Strategy)  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-5  
Team: BE  
Dependencies (Functional): KC-SETUP-2  
UX/UI Design Link: N/A  
Description (Functional): Set up the core authentication library (NextAuth.js) to manage user sessions locally using secure tokens (JWT).  
Acceptance Criteria (Functional):

* User sessions are established upon successful login.  
* Sessions persist across page navigation.  
* Sessions expire after 7 days.  
* Session tokens are stored securely (httpOnly cookies).  
  Technical Approach / Implementation Notes:  
* Create lib/auth.ts. Define and export authOptions: NextAuthOptions.  
* Set providers: \[\] (populated by KC-1.2).  
* Set session: { strategy: 'jwt', maxAge: 7 \* 24 \* 60 \* 60 } // 7 days.  
* Set secret: process.env.NEXTAUTH\_SECRET. Ensure value is generated (openssl rand \-base64 32\) and added to .env and .env.example.  
* Configure pages: { signIn: '/login' }.  
* Configure secure cookie options: cookies: { sessionToken: { name: \\next-auth.session-token\`, options: { httpOnly: true, sameSite: 'lax', path: '/', secure: process.env.NODE\_ENV \=== 'production' } } }\` (secure: false for local HTTP dev).  
* Create app/api/auth/\[...nextauth\]/route.ts and export handlers:  
  import NextAuth from "next-auth";  
  import { authOptions } from "@/lib/auth";

  const handler \= NextAuth(authOptions);

  export { handler as GET, handler as POST };

API Contract (if applicable): N/A (Uses NextAuth endpoints)  
Data Model Changes (if applicable): N/A  
Key Functions/Modules Involved:

* lib/auth.ts  
* app/api/auth/\[...nextauth\]/route.ts  
* .env, .env.example  
  Testing Considerations (Technical): Verify cookie settings (httpOnly, secure=false/true). Test session persistence/expiry.  
  Dependencies (Technical): KC-SETUP-2

Ticket ID: KC-1.2  
Title: Implement NextAuth.js Credentials Provider  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-2  
Team: BE  
Dependencies (Functional): KC-1.1, KC-3.1, KC-2  
UX/UI Design Link: N/A  
Description (Functional): Enable users to log in using their email and password by configuring the authentication library to check credentials against the local database.  
Acceptance Criteria (Functional):

* Users can successfully log in via the Login page using correct email/password.  
* Users receive an appropriate error message on the Login page for incorrect email or password.  
  Technical Approach / Implementation Notes:  
* In lib/auth.ts, import CredentialsProvider, prisma (from @/lib/prisma), comparePassword (from @/lib/security).  
* Add CredentialsProvider({...}) to authOptions.providers.  
* Configure name: 'Credentials', credentials: { email: { label: "Email", type: "email" }, password: { label: "Password", type: "password" } }.  
* Implement async authorize(credentials, req): Promise\<User | null\>:  
  async authorize(credentials) {  
    if (\!credentials?.email || \!credentials?.password) {  
      console.error('Missing credentials');  
      return null; // Or throw an error handled by NextAuth  
    }

    const user \= await prisma.user.findUnique({  
      where: { email: credentials.email },  
    });

    if (\!user || \!user.password) {  
      // Important: Avoid revealing if the user exists or not for security  
      console.error('Invalid credentials (user not found or no password)');  
      return null;  
    }

    const isValid \= await comparePassword(  
      credentials.password,  
      user.password  
    );

    if (\!isValid) {  
      console.error('Invalid credentials (password mismatch)');  
      return null;  
    }

    // Return user object that NextAuth will use to create the session/token  
    // Only return non-sensitive fields  
    return {  
      id: user.id,  
      name: user.name,  
      email: user.email,  
      // image: user.image // if you have images  
    };  
  }

API Contract (if applicable): N/A  
Data Model Changes (if applicable): N/A  
Key Functions/Modules Involved:

* lib/auth.ts  
* lib/prisma.ts  
* lib/security.ts  
  Testing Considerations (Technical): Unit test the authorize function logic (KC-72). Test edge cases (user not found, password field null in DB, invalid password).  
  Dependencies (Technical): KC-1.1, KC-3.1, KC-2

Ticket ID: KC-7.R  
Title: Refactor Login API to use NextAuth.js Credentials Provider  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-2  
Team: BE  
Dependencies (Functional): KC-1.2  
UX/UI Design Link: N/A  
Description (Functional): Ensure the login process uses the standard, secure mechanism provided by the authentication library, removing any old or custom login logic.  
Acceptance Criteria (Functional):

* The login functionality works correctly via the standard NextAuth flow initiated by the frontend.  
* Any previous custom login API endpoints (like /api/auth/login) are removed or disabled.  
  Technical Approach / Implementation Notes:  
* Verify Frontend (KC-AUTH-FE-3) calls signIn('credentials', {...}).  
* Delete app/api/auth/login/route.ts if it exists and contains custom logic separate from NextAuth.  
* Confirm no other code path attempts manual login credential verification outside the NextAuth authorize function.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* (Deletion of) app/api/auth/login/route.ts  
* lib/auth.ts (specifically the authorize function)  
* Frontend login component (KC-AUTH-FE-3)  
  Testing Considerations (Technical): Verify old endpoint returns 404 if deleted. Test login flow end-to-end (KC-AUTH-FE-3).  
  Dependencies (Technical): KC-1.2

Ticket ID: KC-5  
Title: Create API endpoint for User Registration  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-1  
Team: BE  
Dependencies (Functional): KC-3.1, KC-2  
UX/UI Design Link: N/A  
Description (Functional): Provide a way for new users to create an account by submitting their name, email, and password.  
Acceptance Criteria (Functional):

* Sending valid registration details to the API successfully creates a user record.  
* Attempting to register with an existing email results in an error message (e.g., 409 Conflict).  
* Attempting to register with invalid or missing information results in an error message (e.g., 400 Bad Request).  
* User is not automatically logged in after registration.  
  Technical Approach / Implementation Notes:  
* Create app/api/auth/register/route.ts. Export async function POST(request: Request).  
* Import NextResponse from next/server, prisma from @/lib/prisma, hashPassword from @/lib/security, zod for validation.  
* Define Zod schema: const RegisterSchema \= z.object({ name: z.string().max(255).optional(), email: z.string().email(), password: z.string().min(8, { message: "Password must be at least 8 characters long" }) });.  
* Inside POST:  
  * const body \= await request.json();  
  * const validation \= RegisterSchema.safeParse(body);  
  * If \!validation.success, return NextResponse.json({ errors: validation.error.flatten().fieldErrors }, { status: 400 });.  
  * Use try/catch block for database operations.  
  * Check existing user: const existingUser \= await prisma.user.findUnique({ where: { email: validation.data.email } });. If existingUser, return NextResponse.json({ error: 'Email already registered' }, { status: 409 });.  
  * Hash password: const hashedPassword \= await hashPassword(validation.data.password);.  
  * Create user: await prisma.user.create({ data: { ...validation.data, password: hashedPassword } });.  
  * Return NextResponse.json({ message: 'User created successfully' }, { status: 201 });.  
  * In catch block, handle potential Prisma errors (e.g., unique constraint violation if check fails due to race condition \- return 409\) and other errors (return 500). Log errors server-side.  
    API Contract (if applicable):  
* **Endpoint:** POST /api/auth/register  
* **Request Body:** { name?: string, email: string, password: string }  
* **Response Success (201):** { message: string }  
* **Response Error (400):** { errors: { field?: string\[\], ... } } (Zod error format)  
* **Response Error (409):** { error: 'Email already registered' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): Creates User record.  
  Key Functions/Modules Involved:  
* app/api/auth/register/route.ts  
* lib/prisma.ts (Prisma Client)  
* lib/security.ts (hashPassword)  
* zod  
  Testing Considerations (Technical): Unit test validation logic, hashing call, user creation call. Test API endpoint for success, email uniqueness constraint (409), validation errors (400), and server errors (500).  
  Dependencies (Technical): KC-3.1, KC-2

Ticket ID: KC-5.R  
Title: Refactor Registration API Post-Success Flow  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-1  
Team: BE  
Dependencies (Functional): KC-5, KC-1.2  
UX/UI Design Link: N/A  
Description (Functional): Ensure that after a user successfully registers, they are not automatically logged in, requiring them to go through the standard login process.  
Acceptance Criteria (Functional):

* The response from the registration API (POST /api/auth/register) does not include a session token or set a session cookie.  
* The user needs to navigate to the login page and log in separately after registering.  
  Technical Approach / Implementation Notes:  
* Verify the implementation of KC-5 does **not** include any calls to signIn, manual JWT signing, or manual session cookie setting in the success response path.  
* This ticket serves primarily as a verification step to ensure the registration endpoint only creates the user and does not establish a session.  
  API Contract (if applicable): N/A (Verification)  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* app/api/auth/register/route.ts  
  Testing Considerations (Technical): Verify no Set-Cookie header related to the NextAuth session is present in the 201 Created response from the registration API endpoint. Manually test the flow: register \-\> redirect/prompt to login \-\> login successfully.  
  Dependencies (Technical): KC-5, KC-1.2

Ticket ID: KC-8.1  
Title: Configure NextAuth.js JWT Strategy (Callbacks)  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-5  
Team: BE  
Dependencies (Functional): KC-1.1  
UX/UI Design Link: N/A  
Description (Functional): Configure the authentication system to securely include necessary user information (like ID, name, email) within the session token so the application knows who is logged in.  
Acceptance Criteria (Functional):

* When a user logs in, their unique ID, name, and email are available to the application (both backend and frontend) via the session object.  
  Technical Approach / Implementation Notes:  
* In lib/auth.ts \-\> authOptions, add callbacks object.  
* Implement jwt callback: This runs first when a JWT is created or updated. Add custom claims to the token here.  
  async jwt({ token, user, account, profile, isNewUser }) {  
    // \`user\` object is passed on initial sign in  
    if (user) {  
      token.id \= user.id; // Add user ID to the token  
      // Add other fields from \`user\` if needed, e.g., roles  
    }  
    return token; // The token is subsequently encrypted  
  }

* Implement session callback: This runs after the jwt callback. Use data from the token to build the session object accessible on the client.  
  async session({ session, token, user }) {  
    // \`token\` contains the data from the \`jwt\` callback  
    if (token.id && session.user) {  
      session.user.id \= token.id as string; // Add ID to the session user object  
    }  
    // Ensure default fields like name, email are present if needed  
    // session.user.name \= token.name; // Already handled by default? Verify.  
    // session.user.email \= token.email; // Already handled by default? Verify.  
    return session; // The session object is returned to the client  
  }

* Create/Update src/types/next-auth.d.ts to declare the extended Session and JWT interfaces with the custom fields (e.g., id):  
  import { DefaultSession, DefaultUser } from "next-auth";  
  import { JWT, DefaultJWT } from "next-auth/jwt";

  declare module "next-auth" {  
    /\*\*  
     \* Returned by \`useSession\`, \`getSession\` and received as a prop on the \`SessionProvider\` React Context  
     \*/  
    interface Session {  
      user: {  
        /\*\* The user's unique ID. \*/  
        id: string;  
      } & DefaultSession\["user"\]; // Keep default fields like name, email, image  
    }

    // Optional: If your authorize callback returns a User object with id  
    // interface User extends DefaultUser {  
    //   id: string;  
    // }  
  }

  declare module "next-auth/jwt" {  
    /\*\* Returned by the \`jwt\` callback and \`getToken\`, when using JWT sessions \*/  
    interface JWT extends DefaultJWT {  
      /\*\* User ID \*/  
      id?: string;  
      // Add other custom token fields here if needed  
    }  
  }

API Contract (if applicable): Defines session.user structure available client-side: { id: string, name?: string | null, email?: string | null }.  
Data Model Changes (if applicable): N/A  
Key Functions/Modules Involved:

* lib/auth.ts (callbacks object)  
* src/types/next-auth.d.ts  
  Testing Considerations (Technical): Unit test the callback logic (KC-72). Verify session object structure (session.user.id) in Frontend after login using useSession.  
  Dependencies (Technical): KC-1.1

Ticket ID: KC-JWT-Lib.R  
Title: Consolidate JWT Library Usage  
Epic: KC-AUTH  
PRD Requirement(s): NFR-MAINT-1  
Team: BE  
Dependencies (Functional): KC-8.1, KC-7.R, KC-5.R, KC-10.R, KC-Fetch-Cards.1.R (Any ticket potentially using JWTs)  
UX/UI Design Link: N/A  
Description (Functional): Ensure the project uses only one standard way (via the NextAuth.js library) to handle session tokens (JWTs) for consistency and maintainability, removing any direct use of other JWT libraries like jsonwebtoken.  
Acceptance Criteria (Functional):

* The jsonwebtoken library (or similar manual JWT libraries) is not listed as a dependency or used in the project codebase.  
* All session creation, verification, and cookie handling related to user authentication is managed by NextAuth.js.  
  Technical Approach / Implementation Notes:  
* Run npm uninstall jsonwebtoken @types/jsonwebtoken if previously installed and no longer needed for other purposes.  
* Search the entire project codebase (src/) for imports of jsonwebtoken or similar libraries.  
* Refactor any code found to use NextAuth.js mechanisms instead:  
  * For creating sessions: Rely on the signIn flow.  
  * For verifying sessions server-side: Use getServerSession (from next-auth/next) or the helper from KC-8.2.  
  * For accessing session data client-side: Use useSession (from next-auth/react).  
  * For getting the raw JWT token server-side (if absolutely necessary): Use getToken (from next-auth/jwt).  
    API Contract (if applicable): N/A  
    Data Model Changes (if applicable): N/A  
    Key Functions/Modules Involved:  
* All API routes (app/api/...).  
* Any utility functions previously handling JWTs manually.  
* package.json.  
  Testing Considerations (Technical): Run all existing authentication and authorization tests to ensure no regressions after removing manual JWT handling.  
  Dependencies (Technical): KC-8.1, KC-7.R, KC-5.R, KC-10.R, KC-Fetch-Cards.1.R (or any tickets that might have introduced manual JWT handling)

Ticket ID: KC-8.2  
Title: Implement Server-Side Session Check  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-5, NFR-SEC-1  
Team: BE  
Dependencies (Functional): KC-8.1  
UX/UI Design Link: N/A  
Description (Functional): Provide a standard way for backend API endpoints to securely verify if a request comes from a logged-in user and to identify that user.  
Acceptance Criteria (Functional):

* API endpoints requiring login fail with a 401 Unauthorized error if no valid session exists or the session doesn't contain the expected user ID.  
* Backend logic can reliably get the ID of the logged-in user making the request from the session.  
  Technical Approach / Implementation Notes:  
* Create helper lib/sessionUtils.ts:  
  import { getServerSession } from "next-auth/next";  
  import { authOptions } from "@/lib/auth";  
  import { Session } from "next-auth"; // Import Session type

  /\*\*  
   \* Gets the current session object server-side.  
   \* @returns The session object or null if not authenticated.  
   \*/  
  export async function getCurrentSession(): Promise\<Session | null\> {  
    // Ensure you pass the request object if using Pages Router,  
    // but it's automatically handled in App Router API routes.  
    return getServerSession(authOptions);  
  }

  /\*\*  
   \* Gets the current authenticated user's ID server-side.  
   \* Relies on the session callback (KC-8.1) adding \`id\` to \`session.user\`.  
   \* @returns The user ID string or null if not authenticated.  
   \*/  
  export async function getCurrentUserId(): Promise\<string | null\> {  
    const session \= await getCurrentSession();  
    // Use the extended Session type definition from next-auth.d.ts  
    return session?.user?.id ?? null;  
  }

* In protected API route handlers (e.g., app/api/cards/route.ts):  
  import { getCurrentUserId } from "@/lib/sessionUtils";  
  import { NextResponse } from "next/server";

  export async function POST(request: Request) {  
    const userId \= await getCurrentUserId();

    if (\!userId) {  
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });  
    }

    // Proceed with logic using the validated userId...  
    // Example: const cards \= await prisma.card.findMany({ where: { userId } });  
    // ...  
  }

API Contract (if applicable): Standard 401 response for protected endpoints: { error: 'Unauthorized' }.  
Data Model Changes (if applicable): N/A  
Key Functions/Modules Involved:

* All protected API route handlers (e.g., for cards, folders, profile updates).  
* lib/auth.ts (provides authOptions).  
* lib/sessionUtils.ts (new helper file).  
* next-auth/next (getServerSession).  
  Testing Considerations (Technical): Test protected API endpoints with valid session cookies/tokens, without cookies/tokens, and with invalid/expired tokens. Ensure 401 is returned appropriately. Unit test the helper functions (getCurrentSession, getCurrentUserId) by mocking getServerSession.  
  Dependencies (Technical): KC-8.1

Ticket ID: KC-10  
Title: Create API endpoint to fetch current user data (/api/auth/me)  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-6  
Team: BE  
Dependencies (Functional): KC-3.1, KC-8.2  
UX/UI Design Link: N/A  
Description (Functional): Provide a way for the frontend application to get the basic profile information (ID, name, email) of the currently logged-in user.  
Acceptance Criteria (Functional):

* Calling the GET /api/auth/me endpoint returns the current user's ID, name, and email if logged in.  
* The endpoint fails with a 401 Unauthorized error if the user is not logged in.  
* The endpoint fails with a 404 Not Found error if the session is valid but the user record doesn't exist in the DB (edge case).  
  Technical Approach / Implementation Notes:  
* Create app/api/auth/me/route.ts. Export async function GET(request: Request).  
* Import NextResponse, prisma, getCurrentSession from lib/sessionUtils.  
* Inside GET:  
  * const session \= await getCurrentSession();  
  * if (\!session?.user?.id) { return NextResponse.json({ error: 'Unauthorized' }, { status: 401 }); }  
  * const userId \= session.user.id;  
  * Use try/catch for database query.  
  * const user \= await prisma.user.findUnique({ where: { id: userId }, select: { id: true, name: true, email: true } });  
  * if (\!user) { return NextResponse.json({ error: 'User not found' }, { status: 404 }); }  
  * return NextResponse.json({ user });  
  * In catch, log error and return NextResponse.json({ error: 'Internal server error' }, { status: 500 });.  
    API Contract (if applicable):  
* **Endpoint:** GET /api/auth/me  
* **Request:** None (Authentication via session cookie)  
* **Response Success (200):** { user: { id: string, name: string | null, email: string } }  
* **Response Error (401):** { error: 'Unauthorized' }  
* **Response Error (404):** { error: 'User not found' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* app/api/auth/me/route.ts  
* lib/sessionUtils.ts (getCurrentSession)  
* lib/prisma.ts (Prisma Client)  
  Testing Considerations (Technical): Test endpoint with an authenticated user, without authentication (expect 401), and potentially simulate a case where the session exists but the DB user is deleted (expect 404).  
  Dependencies (Technical): KC-3.1, KC-8.2

Ticket ID: KC-10.R  
Title: Refactor /api/auth/me to use NextAuth.js Session  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-6  
Team: BE  
Dependencies (Functional): KC-10, KC-8.2  
UX/UI Design Link: N/A  
Description (Functional): Ensure the API for fetching user data uses the standard authentication check provided by NextAuth.js, potentially simplifying the implementation.  
Acceptance Criteria (Functional):

* The GET /api/auth/me endpoint correctly uses the established server-side session check (e.g., getCurrentSession or getCurrentUserId from KC-8.2).  
* The endpoint can potentially return the user data directly from the session object if all required fields (id, name, email) were added in KC-8.1, avoiding a database call.  
  Technical Approach / Implementation Notes:  
* Review the implementation of KC-10.  
* **Option A (Keep DB call \- current KC-10):** Verify it uses getCurrentSession or getCurrentUserId. This ensures the data is fresh from the DB.  
* **Option B (Use Session Data Only):** If name and email are reliably added to the session in the session callback (KC-8.1), the DB call can be removed:  
  import { getCurrentSession } from "@/lib/sessionUtils";  
  import { NextResponse } from "next/server";

  export async function GET(request: Request) {  
    const session \= await getCurrentSession();

    if (\!session?.user?.id) { // Check for ID specifically  
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });  
    }

    // Return data directly from the session object  
    return NextResponse.json({  
      user: {  
        id: session.user.id,  
        name: session.user.name,  
        email: session.user.email,  
      }  
    });  
  }

* Decision: Choose Option A or B. Option B is slightly more performant but relies on the session data being up-to-date (which it usually is after login, but might lag if user profile is updated elsewhere without a session refresh). Option A guarantees freshness. For Stage 1, either is acceptable, but Option A is slightly more robust against stale session data. This ticket primarily serves as a review/refinement step.  
  API Contract (if applicable): N/A (Verification/Refinement task)  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* app/api/auth/me/route.ts  
* lib/sessionUtils.ts  
  Testing Considerations (Technical): N/A (Covered by KC-10 tests, just verify the chosen implementation).  
  Dependencies (Technical): KC-10, KC-8.2

Ticket ID: KC-12  
Title: Create API endpoint to update user profile data  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-6  
Team: BE  
Dependencies (Functional): KC-3.1, KC-8.2  
UX/UI Design Link: N/A  
Description (Functional): Allow logged-in users to update their profile information, starting with their display name.  
Acceptance Criteria (Functional):

* Sending a valid PUT request to /api/user/profile with a new name updates the user's name in the database.  
* The endpoint fails with 401 Unauthorized if the user is not logged in.  
* The endpoint fails with 400 Bad Request if the provided name is invalid (e.g., empty, too long).  
* The endpoint returns the updated user profile data upon success.  
  Technical Approach / Implementation Notes:  
* Create app/api/user/profile/route.ts. Export async function PUT(request: Request).  
* Import NextResponse, prisma, getCurrentUserId, zod.  
* Define Zod schema: const UpdateProfileSchema \= z.object({ name: z.string().min(1, { message: "Name cannot be empty" }).max(255) });.  
* Inside PUT:  
  * const userId \= await getCurrentUserId();  
  * if (\!userId) { return NextResponse.json({ error: 'Unauthorized' }, { status: 401 }); }  
  * const body \= await request.json();  
  * const validation \= UpdateProfileSchema.safeParse(body);  
  * if (\!validation.success) { return NextResponse.json({ errors: validation.error.flatten().fieldErrors }, { status: 400 }); }  
  * Use try/catch for database update.  
  * const updatedUser \= await prisma.user.update({ where: { id: userId }, data: { name: validation.data.name }, select: { id: true, name: true, email: true } });  
  * Return NextResponse.json({ user: updatedUser });  
  * In catch, log error and return NextResponse.json({ error: 'Internal server error' }, { status: 500 });.  
    API Contract (if applicable):  
* **Endpoint:** PUT /api/user/profile  
* **Request Body:** { name: string }  
* **Response Success (200):** { user: { id: string, name: string | null, email: string } }  
* **Response Error (400):** { errors: { name?: string\[\] } } (Zod error format)  
* **Response Error (401):** { error: 'Unauthorized' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): Updates User.name field.  
  Key Functions/Modules Involved:  
* app/api/user/profile/route.ts  
* lib/sessionUtils.ts (getCurrentUserId)  
* lib/prisma.ts (Prisma Client)  
* zod  
  Testing Considerations (Technical): Test success case, unauthorized case (401), validation error case (400), and server error case (500). Verify the name is actually updated in the database.  
  Dependencies (Technical): KC-3.1, KC-8.2

Ticket ID: KC-AUTH-FE-1  
Title: Create Reusable Auth Form Component  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-1, FR-AUTH-2  
Team: FE  
Dependencies (Functional): KC-AUTH-UX-1, KC-SETUP-3  
UX/UI Design Link: \[Link to Figma/mockups for Auth Form\]  
Description (Functional): Build a standard form component that can be used for both the Login and Registration pages to ensure consistency in UI and validation logic.  
Acceptance Criteria (Functional):

* The component renders input fields for email and password using Chakra UI.  
* It conditionally renders a name input field based on a prop (for registration).  
* It displays a title and submit button text passed in as props.  
* It shows validation errors (required, email format, password length) next to the relevant fields using Chakra UI FormErrorMessage.  
* It displays a general API error message passed in as a prop using Chakra UI Alert.  
* It visually indicates loading state (e.g., disabled button with spinner) via a prop.  
* It uses react-hook-form for form state management and validation (with Zod resolver).  
* It matches the visual design specified in KC-AUTH-UX-1.  
* It is accessible (labels associated with inputs).  
  Technical Approach / Implementation Notes:  
* Create src/components/auth/AuthForm.tsx. Mark as 'use client'.  
* Install dependencies: npm install react-hook-form @hookform/resolvers zod.  
* Use Chakra UI components: Box, VStack, Heading, FormControl, FormLabel, Input, Button, FormErrorMessage, Spinner, Alert, AlertIcon.  
* Define props interface:  
  import { FieldValues, UseFormHandleSubmit } from 'react-hook-form';

  interface AuthFormProps {  
    formType: 'login' | 'register';  
    onSubmit: (data: FieldValues) \=\> Promise\<void\>; // Async submit handler  
    isLoading: boolean;  
    apiError: string | null;  
    title: string;  
    submitButtonText: string;  
  }

* Define Zod schemas (e.g., LoginSchema, RegisterSchema) in a separate file (lib/schemas/auth.ts) or within the component. Use @hookform/resolvers/zod.  
* Use useForm hook with the appropriate schema based on formType.  
* Conditionally render the Name FormControl based on formType.  
* Use register from useForm for inputs. Map formState.errors to FormErrorMessage and isInvalid prop on FormControl.  
* Display apiError prop in an Alert component (status='error') if apiError is not null.  
* Call handleSubmit(props.onSubmit) from useForm on the form's onSubmit.  
* Set isLoading={isLoading || formState.isSubmitting} and isDisabled={isLoading || formState.isSubmitting} on the submit Button. Show Spinner inside button if loading.  
* Ensure htmlFor on FormLabel matches id on Input.  
  API Contract (if applicable): N/A (UI Component)  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/components/auth/AuthForm.tsx  
* Chakra UI components  
* react-hook-form, @hookform/resolvers/zod, zod  
* lib/schemas/auth.ts (optional schema location)  
  Testing Considerations (Technical): Unit test rendering for both form types, validation messages showing on invalid input/submit, onSubmit prop being called with correct data, isLoading state disabling the button, and apiError being displayed (KC-AUTH-TEST-FE-1).  
  Dependencies (Technical): KC-AUTH-UX-1, KC-SETUP-3, react-hook-form, zod, @hookform/resolvers/zod installed.

Ticket ID: KC-AUTH-FE-2  
Title: Implement Registration Page UI & Logic  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-1  
Team: FE  
Dependencies (Functional): KC-AUTH-FE-1, KC-5  
UX/UI Design Link: [https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=0-1\&p=f\&t=oifw4pbxybZKxbMa-0](https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=0-1&p=f&t=oifw4pbxybZKxbMa-0)

Description (Functional): Create the page where new users can sign up for an account using their name, email, and password.  
Acceptance Criteria (Functional):

* A registration page is accessible (e.g., at /register).  
* It uses the reusable AuthForm component configured for registration.  
* Submitting valid details calls the POST /api/auth/register endpoint.  
* Upon successful registration, a success message (e.g., Toast) is shown, and the user is redirected (e.g., to the Login page).  
* Appropriate error messages (validation errors from form, API errors like "Email already exists") are shown if registration fails.  
* The form indicates loading state during the API call.  
  Technical Approach / Implementation Notes:  
* Create page route src/app/register/page.tsx. Mark as 'use client'.  
* Import useState from react, useRouter from next/navigation, useToast from @chakra-ui/react, AuthForm component.  
* Use useState for isLoading and apiError.  
* Implement async function handleRegister(formData: FieldValues):  
  * Set isLoading(true), setApiError(null).  
  * Use try/catch for the fetch call.  
  * const response \= await fetch('/api/auth/register', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(formData) });  
  * If response.ok:  
    * Show success toast: toast({ title: 'Registration successful\!', description: 'Please log in.', status: 'success', ... });  
    * Redirect: router.push('/login');  
  * Else (\!response.ok):  
    * const errorData \= await response.json();  
    * Set setApiError(errorData.error || errorData.message || 'Registration failed'); (Handle different error formats from API).  
  * In catch (error): Set setApiError('An unexpected error occurred.'); Log the actual error.  
  * Finally: setIsLoading(false);  
* Render \<AuthForm formType='register' onSubmit={handleRegister} isLoading={isLoading} apiError={apiError} title="Create Account" submitButtonText="Register" /\>.  
* Wrap page content in layout components (e.g., Center, Box) as per design.  
  API Contract (if applicable): Consumes POST /api/auth/register (KC-5).  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/app/register/page.tsx  
* src/components/auth/AuthForm.tsx  
* next/navigation (useRouter)  
* @chakra-ui/react (useToast)  
  Testing Considerations (Technical): E2E test the complete registration flow (success, email exists, validation errors). Unit test the handleRegister logic (mocking fetch, router, toast).  
  Dependencies (Technical): KC-AUTH-FE-1, KC-5

Ticket ID: KC-AUTH-FE-3  
Title: Implement Login Page UI & Logic  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-2  
Team: FE  
Dependencies (Functional): KC-AUTH-FE-1, KC-1.2  
UX/UI Design Link: [https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=3-86\&p=f\&t=oifw4pbxybZKxbMa-0](https://www.figma.com/design/zpC7fF2JquGvz1gkKjxROE/DPKB--Dynamic-Personal-Knowledge-Base?node-id=3-86&p=f&t=oifw4pbxybZKxbMa-0)

Description (Functional): Create the page where existing users can log in using their email and password.  
Acceptance Criteria (Functional):

* A login page is accessible (e.g., at /login).  
* It uses the reusable AuthForm component configured for login.  
* Submitting correct credentials calls the NextAuth signIn function with the 'credentials' provider.  
* Upon successful login, the user is redirected (e.g., to the dashboard or their intended page).  
* Submitting incorrect credentials shows an appropriate error message on the page (using the apiError prop of AuthForm).  
* The form indicates loading state during the signIn attempt.  
  Technical Approach / Implementation Notes:  
* Create page route src/app/login/page.tsx. Mark as 'use client'.  
* Import useState from react, useRouter, useSearchParams from next/navigation, signIn from next-auth/react, AuthForm component.  
* Use useState for isLoading and apiError.  
* Get potential callback URL from search params: const searchParams \= useSearchParams(); const callbackUrl \= searchParams.get('callbackUrl') || '/dashboard';.  
* Implement async function handleLogin(formData: FieldValues):  
  * Set isLoading(true), setApiError(null).  
  * const result \= await signIn('credentials', { redirect: false, // Handle redirect manually based on result email: formData.email, password: formData.password });  
  * If result?.error:  
    * Map common NextAuth errors: setApiError(result.error \=== 'CredentialsSignin' ? 'Invalid email or password' : result.error);  
  * Else if result?.ok:  
    * Redirect: router.push(callbackUrl);  
  * Else:  
    * Set setApiError('Login failed. Please try again.');  
  * Set setIsLoading(false); (Consider placing in finally block if using try/catch).  
* Render \<AuthForm formType='login' onSubmit={handleLogin} isLoading={isLoading} apiError={apiError} title="Log In" submitButtonText="Login" /\>.  
* Wrap page content in layout components as per design.  
  API Contract (if applicable): Interacts with NextAuth signIn flow, which internally calls the authorize function (KC-1.2).  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/app/login/page.tsx  
* src/components/auth/AuthForm.tsx  
* next-auth/react (signIn)  
* next/navigation (useRouter, useSearchParams)  
  Testing Considerations (Technical): E2E test the login flow (success, failure with wrong credentials). Unit test the handleLogin logic (mocking signIn, router). Test handling of callbackUrl.  
  Dependencies (Technical): KC-AUTH-FE-1, KC-1.2

Ticket ID: KC-AUTH-FE-4  
Title: Implement Client-Side Session Handling  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-5  
Team: FE  
Dependencies (Functional): KC-1.1, KC-SETUP-3  
UX/UI Design Link: N/A (Covers general app behavior like header state, route protection)  
Description (Functional): Ensure the application UI correctly reflects the user's authentication status (logged in/out), provides global login/logout actions, and protects routes that require authentication.  
Acceptance Criteria (Functional):

* A global component (e.g., Header) shows "Login/Register" links/buttons when logged out.  
* The global component shows user-specific elements (e.g., Profile link/menu, Logout button, possibly user name) when logged in.  
* Attempting to access protected pages (e.g., Dashboard, Profile) redirects unauthenticated users to the Login page (preserving the intended destination via callbackUrl).  
* The application state (e.g., header display) updates correctly after login and logout actions.  
* Session state is managed using NextAuth's SessionProvider and useSession hook.  
  Technical Approach / Implementation Notes:  
* **Provider Setup:** In src/app/providers.tsx (created in KC-SETUP-3), import SessionProvider from next-auth/react. Wrap the main {children} with \<SessionProvider\>. Ensure providers.tsx is imported and used in src/app/layout.tsx.  
* **Header Component:** Create src/components/layout/Header.tsx (mark as 'use client').  
  * Use useSession() hook from next-auth/react.  
  * Check session.status:  
    * If 'loading', show placeholder/skeleton.  
    * If 'authenticated', show Link to /profile, user name (session.data.user.name), and Logout button (calls signOut() from next-auth/react, see KC-AUTH-FE-5).  
    * If 'unauthenticated', show Link to /login and /register.  
* **Layout Integration:** Include \<Header /\> in src/app/layout.tsx.  
* **Route Protection (AuthGuard):** Create src/components/auth/AuthGuard.tsx (mark as 'use client').  
  'use client';  
  import { useSession } from 'next-auth/react';  
  import { redirect } from 'next/navigation';  
  import { ReactNode } from 'react';  
  import { Spinner } from '@chakra-ui/react'; // Or your loading component

  interface AuthGuardProps {  
    children: ReactNode;  
  }

  export default function AuthGuard({ children }: AuthGuardProps) {  
    const { status } \= useSession({  
      required: true, // Triggers redirect if unauthenticated  
      onUnauthenticated() {  
        // Redirects to login page, NextAuth handles adding callbackUrl  
        redirect('/login');  
      },  
    });

    if (status \=== 'loading') {  
      // Optional: Show a loading spinner while session is being checked  
      return \<Spinner /\>;  
    }

    // If status is 'authenticated', render the children  
    return \<\>{children}\</\>;  
  }

* **Applying Protection:** Create protected route groups using Next.js App Router conventions. For example, create a folder src/app/(protected)/. Place protected pages (like dashboard, profile) inside this group. Create a layout file for this group: src/app/(protected)/layout.tsx.  
  // src/app/(protected)/layout.tsx  
  import AuthGuard from '@/components/auth/AuthGuard';  
  import { ReactNode } from 'react';

  export default function ProtectedLayout({ children }: { children: ReactNode }) {  
    return \<AuthGuard\>{children}\</AuthGuard\>;  
  }

API Contract (if applicable): Uses NextAuth session endpoint (/api/auth/session) implicitly via useSession.  
Data Model Changes (if applicable): N/A  
Key Functions/Modules Involved:

* src/app/providers.tsx (SessionProvider)  
* src/app/layout.tsx  
* src/components/layout/Header.tsx (useSession, conditional rendering)  
* src/components/auth/AuthGuard.tsx (useSession({ required: true }))  
* Protected route group layout (src/app/(protected)/layout.tsx)  
* next-auth/react (SessionProvider, useSession, signOut)  
* next/navigation (redirect)  
  Testing Considerations (Technical): E2E tests for route protection (redirecting unauthenticated users) and conditional header rendering based on auth status. Unit tests for AuthGuard and Header components (mocking useSession return values).  
  Dependencies (Technical): KC-1.1, KC-SETUP-3

Ticket ID: KC-AUTH-FE-5  
Title: Implement Basic Profile Page UI  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-6  
Team: FE  
Dependencies (Functional): KC-AUTH-FE-4 (Session Handling/Header), KC-8.1 (for session data structure)  
UX/UI Design Link: \[Link to Figma/mockups for Profile Page\]  
Description (Functional): Create a page, accessible only to logged-in users, where they can view their basic account details (name, email) and initiate the logout process.  
Acceptance Criteria (Functional):

* A profile page is accessible (e.g., at /profile) only to logged-in users (protected by AuthGuard).  
* The page displays the user's current name and email address obtained from the session.  
* A "Logout" button is present and functional.  
* Clicking "Logout" calls the NextAuth signOut function, successfully logs the user out, and redirects them (e.g., to the homepage or login page).  
  Technical Approach / Implementation Notes:  
* Create page route src/app/(protected)/profile/page.tsx. Mark as 'use client'.  
* Import useSession, signOut from next-auth/react.  
* Import Chakra UI components (Box, VStack, Heading, Text, Button, Spinner).  
* Use the useSession() hook. The AuthGuard in the layout handles the initial loading and unauthenticated redirect.  
* Inside the component:  
  * const { data: session, status } \= useSession();  
  * If status \=== 'loading', return \<Spinner /\> (or null, as AuthGuard might handle this).  
  * If status \=== 'authenticated' && session?.user:  
    * Display user details: session.user.name || 'N/A', session.user.email. Use Chakra Heading, Text, etc.  
    * Add Logout Button: \<Button onClick={() \=\> signOut({ callbackUrl: '/' })}\>Logout\</Button\>. Specify callbackUrl for redirection after logout.  
  * Handle the case where status is authenticated but session data is somehow missing (optional, fallback UI).  
* Wrap content in layout components as per design.  
  API Contract (if applicable): Uses NextAuth session data. Uses signOut function which calls /api/auth/signout.  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/app/(protected)/profile/page.tsx  
* src/components/auth/AuthGuard.tsx (used in layout)  
* next-auth/react (useSession, signOut)  
* Chakra UI components  
  Testing Considerations (Technical): E2E test the profile page access (should succeed for logged-in, redirect for logged-out). Test profile information display. Test logout button functionality and redirection. Unit test component rendering based on mocked useSession data (authenticated state).  
  Dependencies (Technical): KC-AUTH-FE-4, KC-8.1

Ticket ID: KC-AUTH-FE-6  
Title: Implement Basic Profile Update UI  
Epic: KC-AUTH  
PRD Requirement(s): FR-AUTH-6  
Team: FE  
Dependencies (Functional): KC-AUTH-FE-5, KC-12  
UX/UI Design Link: \[Link to Figma/mockups for Profile Page Update Section\]  
Description (Functional): Enhance the profile page to allow users to change their display name.  
Acceptance Criteria (Functional):

* The profile page (/profile) includes an editable form field for the user's name, pre-filled with the current name.  
* The form uses react-hook-form for state and validation (e.g., name not empty).  
* Submitting a valid new name calls the PUT /api/user/profile endpoint.  
* A success message (e.g., Toast) is shown upon successful update.  
* The displayed name on the profile page (and potentially the Header) updates automatically after a successful update (using NextAuth's session update function).  
* Error messages are shown if the update fails (validation errors, API errors).  
* Loading state is indicated during the API call.  
  Technical Approach / Implementation Notes:  
* Modify src/app/(protected)/profile/page.tsx (from KC-AUTH-FE-5).  
* Import useForm, FieldValues from react-hook-form, zodResolver from @hookform/resolvers/zod, zod (for schema), useState, useToast.  
* Define Zod schema for the update form (e.g., UpdateProfileSchema \= z.object({ name: z.string().min(1).max(255) });).  
* Use useSession() hook to get current name for default form value and the update function: const { data: session, update } \= useSession();.  
* Use useState for isLoading, apiError.  
* Setup react-hook-form: const { register, handleSubmit, formState: { errors, isSubmitting } } \= useForm({ resolver: zodResolver(UpdateProfileSchema), defaultValues: { name: session?.user?.name || '' } });.  
* Implement onSubmit handler: async function handleUpdateProfile(formData: FieldValues)  
  * setIsLoading(true); setApiError(null);  
  * try { ... await fetch('/api/user/profile', { method: 'PUT', ... body: JSON.stringify(formData) }); ... } catch { ... } finally { setIsLoading(false); }  
  * On success (response.ok):  
    * Show success toast.  
    * **Crucially, update the session:** await update({ name: formData.name }); This triggers NextAuth to refetch the session, updating session.data and components using useSession.  
  * On failure (\!response.ok): Set apiError from response.  
* Render the form using Chakra UI (FormControl, Input, Button, FormErrorMessage) integrated with react-hook-form (register, errors).  
* Disable submit button based on isLoading || isSubmitting.  
  API Contract (if applicable): Consumes PUT /api/user/profile (KC-12).  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/app/(protected)/profile/page.tsx  
* Chakra UI components  
* react-hook-form, zod, @hookform/resolvers/zod  
* next-auth/react (useSession including the update function)  
  Testing Considerations (Technical): E2E test the profile update flow (change name, save, verify update persists and reflects in header/page). Unit test the form submission logic (handleUpdateProfile), mocking fetch, session.update, and toast. Test validation.  
  Dependencies (Technical): KC-AUTH-FE-5, KC-12

Ticket ID: KC-72  
Title: Write Unit Tests for Authentication Logic  
Epic: KC-AUTH  
PRD Requirement(s): NFR-MAINT-1  
Team: BE/QA  
Dependencies (Functional): KC-1.2, KC-8.1  
UX/UI Design Link: N/A  
Description (Functional): Create automated unit tests for the backend authentication logic (NextAuth configuration: Credentials provider authorize function, JWT/Session callbacks) to ensure correctness and prevent regressions.  
Acceptance Criteria (Functional):

* Automated tests verify the authorize function returns the correct user object for valid credentials.  
* Tests verify authorize returns null for invalid email or password.  
* Tests verify the jwt callback adds the user id to the token.  
* Tests verify the session callback adds the user id from the token to the session object.  
  Technical Approach / Implementation Notes:  
* Use Jest/Vitest framework (setup in KC-TEST-FE-1, but configure for backend tests if needed, or use separate config). Create test file src/lib/auth.test.ts.  
* **Mock Dependencies:**  
  * Mock Prisma Client: jest.mock('@/lib/prisma', () \=\> ({ prisma: { user: { findUnique: jest.fn() } } }));  
  * Mock Security Utils: jest.mock('@/lib/security', () \=\> ({ comparePassword: jest.fn() }));  
* **Import Mocks and Target:** import { prisma } from '@/lib/prisma'; import { comparePassword } from '@/lib/security'; import { authOptions } from '@/lib/auth';  
* **Test authorize function:**  
  * Get the function: const authorize \= authOptions.providers.find(p \=\> p.id \=== 'credentials')?.authorize; Check if authorize exists.  
  * Write test cases:  
    * it('should return user object for valid credentials'): Mock prisma.user.findUnique to return a user object, mock comparePassword to return true. Call authorize(validCredentials). Assert the returned object matches expected structure (id, name, email).  
    * it('should return null for non-existent user'): Mock prisma.user.findUnique to return null. Call authorize(credentials). Assert return value is null.  
    * it('should return null for invalid password'): Mock prisma.user.findUnique to return user, mock comparePassword to return false. Call authorize(credentials). Assert return value is null.  
    * it('should return null for missing credentials'): Call authorize({}). Assert return value is null.  
* **Test jwt callback:**  
  * Get the callback: const jwtCallback \= authOptions.callbacks?.jwt; Check if exists.  
  * Call jwtCallback({ token: {}, user: { id: 'user123' } }). Assert the returned token includes { id: 'user123' }.  
* **Test session callback:**  
  * Get the callback: const sessionCallback \= authOptions.callbacks?.session; Check if exists.  
  * Call sessionCallback({ session: { user: {}, expires: '' }, token: { id: 'token123' } }). Assert the returned session includes { user: { id: 'token123' } }.  
    API Contract (if applicable): N/A  
    Data Model Changes (if applicable): N/A  
    Key Functions/Modules Involved:  
* lib/auth.ts (authOptions)  
* Jest/Vitest, jest.fn, jest.mock  
* Mocked Prisma client and security utils.  
  Testing Considerations (Technical): Ensure mocks cover all relevant scenarios and return values. Reset mocks between tests (beforeEach). Handle async nature of functions (async/await).  
  Dependencies (Technical): KC-1.2, KC-8.1, Testing framework setup.

Ticket ID: KC-AUTH-TEST-BE-1
Title: Write Integration Tests for Registration API (/api/auth/register)
Epic: KC-AUTH
PRD Requirement(s): NFR-MAINT-1
Team: BE/QA
Dependencies (Functional): KC-5 (Registration API), KC-TEST-BE-1 (BE Test Setup)
UX/UI Design Link: N/A
Description (Functional): Create automated integration tests to verify the functionality and error handling of the user registration API endpoint.
Acceptance Criteria (Functional):
* Tests verify successful user creation (201 status) with valid data.
* Tests verify validation errors (400 status) for missing/invalid email, password (including policy checks).
* Tests verify conflict error (409 status) when attempting to register an existing email.
* Tests verify the API does *not* automatically log the user in (no session cookie returned on 201).
* Tests cover basic database error handling (500 status).
Technical Approach / Implementation Notes:
* Use Jest/Vitest and Supertest (or similar for HTTP requests).
* Interact with a test database.
* Seed test data (e.g., existing user for conflict test).
* Clean up test data after tests.
* Test cases: Success, invalid email, invalid password (length, complexity), missing fields, duplicate email, database error during create.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `/app/api/auth/register/route.ts`, Test framework, Test DB utilities.
Testing Considerations (Technical): Focus on API contract and behavior, mocking external dependencies if any, but interacting with real DB.
Dependencies (Technical): KC-5, KC-TEST-BE-1

Ticket ID: KC-AUTH-TEST-BE-2
Title: Write Integration Tests for Get Profile API (/api/auth/me)
Epic: KC-AUTH
PRD Requirement(s): NFR-MAINT-1
Team: BE/QA
Dependencies (Functional): KC-10 (Get Profile API), KC-TEST-BE-1 (BE Test Setup), KC-8.2 (Session Utils)
UX/UI Design Link: N/A
Description (Functional): Create automated integration tests to verify the functionality of the API endpoint for fetching the current user's profile data based on their session.
Acceptance Criteria (Functional):
* Tests verify successful retrieval (200 status) of authenticated user's data (id, name, email) based on mocked session.
* Tests verify the API returns 401 Unauthorized if no valid session exists (mocked session utility returns null).
* Tests verify the API implementation *only* relies on session data (mocks session utility, asserts no DB call occurs).
Technical Approach / Implementation Notes:
* Use Jest/Vitest and Supertest.
* Mock the `getCurrentSession` utility (from KC-8.2) to simulate authenticated and unauthenticated states.
* Test cases: Authenticated user (mock session returns user data), Unauthenticated user (mock session returns null).
* Assert response status codes and body content based on mocked session data.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `/app/api/auth/me/route.ts`, Mocked `lib/sessionUtils.ts`.
Testing Considerations (Technical): Focus on testing the API's reliance on the mocked session utility and correct response formatting.
Dependencies (Technical): KC-10, KC-TEST-BE-1, KC-8.2

Ticket ID: KC-AUTH-TEST-BE-3
Title: Write Integration Tests for Update Profile API (/api/user/profile)
Epic: KC-AUTH
PRD Requirement(s): NFR-MAINT-1
Team: BE/QA
Dependencies (Functional): KC-12 (Update Profile API), KC-TEST-BE-1 (BE Test Setup)
UX/UI Design Link: N/A
Description (Functional): Create automated integration tests to verify the functionality and error handling of the API endpoint for updating a user's profile information.
Acceptance Criteria (Functional):
* Tests verify successful profile update (e.g., name change) for an authenticated user (200 status, returns updated user).
* Tests verify validation errors (400 status) for invalid input (e.g., empty name).
* Tests verify authentication check (401 status if user not logged in).
* Tests cover database error handling (500 status).
Technical Approach / Implementation Notes:
* Use Jest/Vitest and Supertest.
* Interact with a test database.
* Seed test user data.
* Mock authentication (e.g., `getCurrentUserId` from KC-8.2).
* Test cases: Success (update name), invalid name, unauthenticated user, database error during update.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `/app/api/user/profile/route.ts`, Mocked `lib/sessionUtils.ts`, Test DB utilities.
Testing Considerations (Technical): Verify database record is updated correctly on success. Test validation logic.
Dependencies (Technical): KC-12, KC-TEST-BE-1

Ticket ID: KC-AUTH-TEST-FE-2
Title: Write Integration Tests for Registration Page
Epic: KC-AUTH
PRD Requirement(s): NFR-MAINT-1
Team: FE/QA
Dependencies (Functional): KC-AUTH-FE-2 (Registration Page), KC-TEST-FE-1 (FE Test Setup)
UX/UI Design Link: N/A
Description (Functional): Create automated integration tests for the Registration page UI and its interaction logic, including form submission and handling API responses.
Acceptance Criteria (Functional):
* Tests verify the registration form renders correctly.
* Tests verify form submission with valid data triggers API call (`POST /api/auth/register`).
* Tests verify successful API response shows success toast and redirects to login.
* Tests verify API error responses (validation, conflict) display appropriate error messages on the form/toast.
* Tests verify form validation prevents submission with invalid data.
Technical Approach / Implementation Notes:
* Use Jest/Vitest and React Testing Library.
* Mock `fetch` to simulate API responses (success 201, error 400, error 409).
* Mock `useRouter` and `useToast`.
* Simulate user input and form submission events.
* Assert API calls, toast messages, router actions, and error message display based on simulated API responses.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `src/app/register/page.tsx`, `src/components/auth/AuthForm.tsx`, Mocked `fetch`, `useRouter`, `useToast`.
Testing Considerations (Technical): Focus on UI interaction, state changes, and handling of mocked API responses.
Dependencies (Technical): KC-AUTH-FE-2, KC-TEST-FE-1

Ticket ID: KC-AUTH-TEST-FE-3
Title: Write Integration Tests for Login Page
Epic: KC-AUTH
PRD Requirement(s): NFR-MAINT-1
Team: FE/QA
Dependencies (Functional): KC-AUTH-FE-3 (Login Page), KC-TEST-FE-1 (FE Test Setup)
UX/UI Design Link: N/A
Description (Functional): Create automated integration tests for the Login page UI and its interaction logic, including form submission and handling NextAuth `signIn` responses.
Acceptance Criteria (Functional):
* Tests verify the login form renders correctly.
* Tests verify form submission with valid data triggers NextAuth `signIn('credentials', ...)`.
* Tests verify successful `signIn` result redirects user (e.g., to dashboard).
* Tests verify `signIn` error result (e.g., 'CredentialsSignin') displays appropriate error message on the form/toast.
* Tests verify form validation prevents submission with invalid data.
Technical Approach / Implementation Notes:
* Use Jest/Vitest and React Testing Library.
* Mock `signIn` from `next-auth/react` to simulate success and error responses.
* Mock `useRouter` and `useToast`.
* Simulate user input and form submission events.
* Assert `signIn` calls, router actions, toast messages, and error message display based on simulated `signIn` responses.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `src/app/login/page.tsx`, `src/components/auth/AuthForm.tsx`, Mocked `signIn`, `useRouter`, `useToast`.
Testing Considerations (Technical): Focus on UI interaction, state changes, and handling of mocked `signIn` function.
Dependencies (Technical): KC-AUTH-FE-3, KC-TEST-FE-1

Ticket ID: KC-AUTH-TEST-FE-4
Title: Write Integration Tests for Profile Page (View & Update)
Epic: KC-AUTH
PRD Requirement(s): NFR-MAINT-1
Team: FE/QA
Dependencies (Functional): KC-AUTH-FE-5 (Profile Page View), KC-AUTH-FE-6 (Profile Page Update), KC-TEST-FE-1 (FE Test Setup)
UX/UI Design Link: N/A
Description (Functional): Create automated integration tests for the Profile page, covering both displaying user data fetched from the API and handling the profile update functionality.
Acceptance Criteria (Functional):
* Tests verify the page fetches and displays user data (`GET /api/auth/me`) correctly.
* Tests verify the update form allows input and submission.
* Tests verify submitting the update form triggers the API call (`PUT /api/user/profile`).
* Tests verify successful API update shows success toast and potentially updates displayed data.
* Tests verify API errors during update are handled gracefully (toast/message).
Technical Approach / Implementation Notes:
* Use Jest/Vitest and React Testing Library.
* Mock `fetch` for both `GET /api/auth/me` and `PUT /api/user/profile`.
* Mock `useToast`.
* Simulate initial load to verify data display.
* Simulate form input and submission for update functionality.
* Assert API calls, state changes, and toast messages.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `src/app/(protected)/profile/page.tsx`, Mocked `fetch`, `useToast`.
Testing Considerations (Technical): Cover both view and update flows, including loading and error states for API calls.
Dependencies (Technical): KC-AUTH-FE-5, KC-AUTH-FE-6, KC-TEST-FE-1

Ticket ID: KC-AUTH-TEST-FE-5
Title: Write Unit Tests for AuthGuard and Header Components
Epic: KC-AUTH
PRD Requirement(s): NFR-MAINT-1
Team: FE/QA
Dependencies (Functional): KC-AUTH-FE-4 (Session Handling/Header), KC-AUTH-FE-4 (AuthGuard Implied), KC-TEST-FE-1 (FE Test Setup)
UX/UI Design Link: N/A
Description (Functional): Create automated unit tests for key authentication-related UI components like the AuthGuard (if implemented as a component) and the Header component that displays conditional login/logout elements.
Acceptance Criteria (Functional):
* Tests verify the Header component correctly renders Login/Register links when unauthenticated.
* Tests verify the Header component correctly renders Profile/Logout elements when authenticated.
* Tests verify the Header component handles the loading state from `useSession`.
* (If applicable) Tests verify the AuthGuard component correctly handles different session states (loading, authenticated, unauthenticated) and triggers redirects or renders children appropriately.
Technical Approach / Implementation Notes:
* Use Jest/Vitest and React Testing Library.
* Mock `useSession` hook from `next-auth/react` to simulate different authentication states (loading, data: null, data: { user: ... }).
* Mock `useRouter` if testing redirects in AuthGuard.
* Mock `signOut` if testing logout button functionality.
* Assert component rendering based on mocked session states.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `src/components/layout/Header.tsx`, `src/components/auth/AuthGuard.tsx` (if exists), Mocked `useSession`, `useRouter`, `signOut`.
Testing Considerations (Technical): Focus on component rendering logic based on different mocked session states.
Dependencies (Technical): KC-AUTH-FE-4, KC-TEST-FE-1