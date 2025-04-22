# **Review and AI Prompts for KC-AUTH Epic (Stage 1\) \- Updated**

This document contains the technical review and AI development prompts for the KC-AUTH epic (Stage 1), updated based on recent decisions.

## **Part 1: Tech Lead Review of KC-AUTH Epic (Stage 1\) \- Updated**

This epic focuses on the critical user authentication and basic profile features for the initial local stage.

**A. Alignment and Coverage:**

* **PRD/TDD/ADRs:** The tickets align well with PRD requirements (FR-AUTH-\*), TDD, and ADRs (Next.js, PostgreSQL/Prisma, NextAuth.js, JWT session strategy, Chakra UI, Jest). Figma links included.  
* **Completeness:** Covers design, schema, backend API/auth logic, frontend pages/components, session handling, and initial testing.

**B. Overlaps, Gaps, and Clarifications:**

* **Overlap with KC-SETUP-5:**  
  * **Decision:** Treat **KC-SETUP-5** as the primary ticket for defining the initial schema (User, Account, Session, VerificationToken, Card, Tag, Folder). Treat **KC-3.1** as a *verification* step within this epic to ensure the User model meets local auth requirements before implementing auth logic. The prompt for KC-3.1 reflects this.  
* **Registration API (KC-5) vs. NextAuth:** Custom registration API (/api/auth/register) alongside NextAuth requires careful implementation. KC-5.R (verifying no auto-login) is crucial. Frontend (KC-AUTH-FE-2) must call the custom endpoint for registration.  
* **Missing Tests (Action Taken):** Added new tickets to address testing gaps:  
  * **Backend API Tests:**  
    * KC-AUTH-TEST-BE-1: Write Integration Tests for Registration API (/api/auth/register)  
    * KC-AUTH-TEST-BE-2: Write Integration Tests for Get Profile API (/api/auth/me)  
    * KC-AUTH-TEST-BE-3: Write Integration Tests for Update Profile API (/api/user/profile)  
  * **Frontend Page/Integration Tests:**  
    * KC-AUTH-TEST-FE-2: Write Integration Tests for Registration Page  
    * KC-AUTH-TEST-FE-3: Write Integration Tests for Login Page  
    * KC-AUTH-TEST-FE-4: Write Integration Tests for Profile Page (View & Update)  
    * KC-AUTH-TEST-FE-5: Write Unit Tests for AuthGuard and Header Components

**C. Decisions Made / Discrepancies Resolved:**

* **Password Policy Discrepancy (KC-5):**  
  * **Decision:** The password policy is **minimum 6 characters** with complexity requirements (1 upper, 1 lower, 1 number, 1 special char), aligning with the Security Document.  
  * **Action:** The Zod schema validation in KC-5 prompt is updated to reflect this policy, requiring a regex or custom refinement, *not* just min(8).  
* **/api/auth/me Implementation (KC-10.R):**  
  * **Decision:** Implement **Option B** (rely solely on session data) for the /api/auth/me endpoint.  
  * **Action:** The prompt for KC-10.R is updated to instruct implementation using session data directly, removing the database call. This prioritizes potential performance over guaranteed data freshness for this specific endpoint.  
* **Session Strategy:**  
  * **Decision:** The project will use the **JWT session strategy** provided by NextAuth.js, as implicitly defined in tickets KC-1.1 and KC-8.1.  
  * **Rationale:** JWT offers statelessness (beneficial for scaling) and reduced database load for session verification compared to database sessions. While revocation and data staleness require consideration, NextAuth.js provides tools to manage these (callbacks, client-side updates). This aligns with common practices for Next.js applications.

**D. Implicit Decisions (Confirmed):**

* Session Strategy: Confirmed as JWT (see above).

*(Note: The addition of testing tickets should be reflected in the master project plan/TDD).*

## **Part 2: AI Development Prompts for KC-AUTH Epic (Stage 1\) \- Updated**

*(Prompts reference the full suite of project documents and incorporate review findings and decisions)*

**1\. Ticket: KC-AUTH-UX-1: Design Authentication User Flow & Components (Local Focus)**

* **Prompt (For TL/Dev Reference):** Review the UX designs and flows for Registration, Login, and Profile pages provided in **JIRA Ticket KC-AUTH-UX-1** (Figma Links included). Ensure designs align with **ADR-006 (Chakra UI)** and the **UI Style Guide**. Pay close attention to component states (inputs, buttons), error message definitions, accessibility considerations (contrast, focus, labels), and responsiveness. These designs will be the primary visual reference for implementing tickets KC-AUTH-FE-1, KC-AUTH-FE-2, KC-AUTH-FE-3, KC-AUTH-FE-5, KC-AUTH-FE-6.

**2\. Ticket: KC-3.1: Verify User Schema in Prisma**

* **Prompt:** Verify and refine the User model definition within prisma/schema.prisma as specified in **JIRA Ticket KC-3.1**, ensuring it meets all requirements for local authentication logic (tickets KC-1.2, KC-5, KC-10, KC-12).  
  * Confirm the presence and correct types for id, name (optional string), email (unique string), password (string), createdAt, updatedAt.  
  * Ensure relations (cards, folders) are defined as needed for Stage 1\.  
  * Confirm alignment with models potentially added for NextAuth adapter (Account, Session, VerificationToken from **KC-SETUP-5**) even if using JWT strategy, to avoid future conflicts.  
  * **This task primarily verifies the schema defined in KC-SETUP-5 is adequate before implementing auth logic.** Minor refinements specific to auth fields are acceptable.  
  * If changes are made, run npx prisma format and npx prisma migrate dev \--name refine-user-model. Run npx prisma generate.  
  * Aligns with **ADR-002**.

**3\. Ticket: KC-2: Implement Password Hashing using bcryptjs**

* **Prompt:** Implement password hashing and comparison functions using bcryptjs as specified in **JIRA Ticket KC-2**, fulfilling **PRD Requirement FR-AUTH-4**.  
  1. Create src/lib/security.ts.  
  2. Implement hashPassword(password: string): Promise\<string\> using bcrypt.hash with a salt factor of 10\.  
  3. Implement comparePassword(plain: string, hashed: string): Promise\<boolean\> using bcrypt.compare.  
  4. Install types if not already present: npm install \-D @types/bcryptjs.  
  5. Ensure implementation adheres to **Coding Standards Section 4** and **Security Document Section 3.1**.  
  6. Write basic unit tests for these two functions (e.g., in src/lib/security.test.ts).

**4\. Ticket: KC-1.1: Configure NextAuth.js Core Setup (Local JWT Strategy)**

* **Prompt:** Configure the core NextAuth.js options for a local JWT session strategy as specified in **JIRA Ticket KC-1.1**, fulfilling **PRD Requirement FR-AUTH-5**.  
  1. Create src/lib/auth.ts and define/export authOptions: NextAuthOptions.  
  2. Set providers: \[\] (to be populated in KC-1.2).  
  3. Set session: { strategy: 'jwt', maxAge: 7 \* 24 \* 60 \* 60 } (7 days).  
  4. Set secret: process.env.NEXTAUTH\_SECRET (ensure value exists in .env from KC-SETUP-2).  
  5. Configure pages: { signIn: '/login' }.  
  6. Configure secure cookie options as specified (httpOnly: true, secure: process.env.NODE\_ENV \=== 'production', sameSite: 'lax'). Refer to Security Document Section 3.5.  
  7. Create the NextAuth API route handler src/app/api/auth/\[...nextauth\]/route.ts exporting GET and POST handlers using NextAuth(authOptions).

5\. Ticket: KC-1.2: Implement NextAuth.js Credentials Provider

* Prompt: Implement the NextAuth.js CredentialsProvider for email/password login as specified in JIRA Ticket KC-1.2, fulfilling PRD Requirement FR-AUTH-2.  
  1. In src/lib/auth.ts (from KC-1.1), import CredentialsProvider, prisma (from singleton KC-SETUP-8), and comparePassword (from KC-2).  
  2. Add CredentialsProvider to the authOptions.providers array.  
  3. Configure its name ('credentials') and credentials fields (email, password).  
  4. Implement the async authorize(credentials) function:  
     * Validate credentials.email and credentials.password exist.  
     * Fetch the user from the database using prisma.user.findUnique({ where: { email } }).  
     * Securely compare the provided password with the stored hash using comparePassword. Return null if user not found or password mismatch (avoid revealing which).  
     * On success, return a user object containing non-sensitive fields needed for the session/token (e.g., id, name, email), aligning with the types defined in src/types/next-auth.d.ts (KC-8.1).  
  5. Ensure error handling is robust and doesn't leak information, following Security Document Section 3.1 & 3.9.

6\. Ticket: KC-7.R: Refactor Login API to use NextAuth.js Credentials Provider

* Prompt: Verify and ensure the application's login flow exclusively uses the NextAuth.js Credentials Provider mechanism set up in KC-1.2, as specified in JIRA Ticket KC-7.R.  
  1. Confirm the frontend login page (KC-AUTH-FE-3) calls signIn('credentials', {...}) from next-auth/react.  
  2. Search for and delete any custom backend API route specifically designed for handling login POST requests (e.g., app/api/auth/login/route.ts) if it exists and contains logic separate from the NextAuth authorize function.  
  3. Verify no other code paths attempt manual credential checks outside the configured NextAuth provider.  
  4. Run relevant E2E tests (KC-AUTH-TEST-FE-3) to confirm login still works correctly via the standard NextAuth flow and any old endpoint is non-functional (returns 404).

7\. Ticket: KC-5: Create API endpoint for User Registration

* Prompt: Implement the standalone API endpoint for user registration at POST /api/auth/register as specified in JIRA Ticket KC-5, fulfilling PRD Requirement FR-AUTH-1.  
  1. Create app/api/auth/register/route.ts exporting an async POST function.  
  2. Import NextResponse, prisma (from KC-SETUP-8), hashPassword (from KC-2), and zod.  
  3. Define a Zod schema (RegisterSchema) for the request body (name?, email, password).  
     * Crucially, implement password validation according to the agreed policy: minimum 6 characters, 1 uppercase, 1 lowercase, 1 number, 1 special character. Use z.string().min(6) and .refine() or .regex() to enforce complexity rules. Refer to Security Doc Section 3.1. Do NOT use just min(8).  
  4. Parse and validate the request body using RegisterSchema.safeParse. Return 400 on validation failure with Zod error details.  
  5. Check if email already exists using prisma.user.findUnique. Return 409 Conflict if it exists.  
  6. Hash the validated password using hashPassword.  
  7. Create the user using prisma.user.create, storing the hashed password.  
  8. Return 201 Created with a success message on successful creation. Do not attempt to log the user in or return session tokens (as per KC-5.R).  
  9. Implement robust try/catch error handling for database operations and other errors, returning 500 status code and logging errors server-side (Coding Standards Section 4.4, Security Doc Section 3.9).

8\. Ticket: KC-5.R: Refactor Registration API Post-Success Flow

* Prompt: Verify the implementation of the registration API endpoint (POST /api/auth/register from KC-5) strictly adheres to the requirement of *not* automatically logging the user in, as specified in JIRA Ticket KC-5.R.  
  1. Review the code in app/api/auth/register/route.ts.  
  2. Confirm there are absolutely no calls to signIn, manual JWT signing functions, or attempts to set session cookies in the success (201 Created) response path.  
  3. Verify through testing (manual or automated KC-AUTH-TEST-BE-1) that the 201 response does not contain any session-related data or Set-Cookie headers for the NextAuth session.

9\. Ticket: KC-8.1: Configure NextAuth.js JWT Strategy (Callbacks)

* Prompt: Configure NextAuth.js JWT and Session callbacks to include necessary user information in the session, as specified in JIRA Ticket KC-8.1, fulfilling PRD Requirement FR-AUTH-5.  
  1. In src/lib/auth.ts \-\> authOptions, add the callbacks object.  
  2. Implement the async jwt({ token, user, trigger, session }) callback:  
     * On initial sign-in (user object exists), add user.id, user.name, user.email to the token.  
     * Handle session updates (trigger \=== 'update' && session): merge session data (like updated name) into the token.  
     * Return the modified token.  
  3. Implement the async session({ session, token }) callback:  
     * If token.id, token.name, token.email exist, add them to the session.user object (e.g., session.user.id \= token.id as string, session.user.name \= token.name as string | null, session.user.email \= token.email as string).  
     * Return the modified session.  
  4. Create or update src/types/next-auth.d.ts to declare the extended Session interface (with user.id: string, user.name: string | null, user.email: string) and the extended JWT interface (with id?: string, name?: string | null, email?: string) as shown in the ticket's technical approach.

10\. Ticket: KC-JWT-Lib.R: Consolidate JWT Library Usage

* Prompt: Ensure the project exclusively uses NextAuth.js for handling authentication JWTs, removing any manual usage of libraries like jsonwebtoken, as specified in JIRA Ticket KC-JWT-Lib.R and supporting NFR-MAINT-1.  
  1. Run npm uninstall jsonwebtoken @types/jsonwebtoken if they are present in package.json and not required for other non-auth purposes.  
  2. Search the entire codebase (src/) for any imports or usage of jsonwebtoken or similar manual JWT libraries.  
  3. Refactor any identified code to use NextAuth.js mechanisms: signIn flow for session creation, getServerSession or helper (KC-8.2) for server-side verification, useSession for client-side access, getToken for rare server-side raw token access.  
  4. Verify authentication and authorization functionality remains intact by running relevant tests (KC-72, KC-AUTH-TEST-BE-\*, KC-AUTH-TEST-FE-\*).

11\. Ticket: KC-8.2: Implement Server-Side Session Check

* Prompt: Implement reusable helper functions for securely checking user sessions on the server-side, as specified in JIRA Ticket KC-8.2, fulfilling PRD Requirement FR-AUTH-5 and NFR-SEC-1.  
  1. Create src/lib/sessionUtils.ts.  
  2. Import getServerSession from next-auth/next and authOptions from @/lib/auth.  
  3. Implement async function getCurrentSession(): Promise\<Session | null\> using getServerSession(authOptions).  
  4. Implement async function getCurrentUser(): Promise\<Session\['user'\] | null\> that calls getCurrentSession and returns session?.user ?? null, relying on the extended Session type from KC-8.1.  
  5. Implement async function getCurrentUserId(): Promise\<string | null\> that calls getCurrentUser and returns user?.id ?? null.  
  6. In examples of protected API routes (e.g., within the ticket description or a sample route), demonstrate how to use getCurrentUserId or getCurrentUser to check for authentication and return a 401 NextResponse if the user/ID is null.

12\. Ticket: KC-10: Create API endpoint to fetch current user data (/api/auth/me)

* Prompt: Implement the API endpoint GET /api/auth/me to fetch basic profile data for the currently logged-in user, as specified in JIRA Ticket KC-10, fulfilling PRD Requirement FR-AUTH-6. This implementation will follow Option B (Session Data Only) as per decision in KC-10.R.  
  1. Create app/api/auth/me/route.ts exporting an async GET function.  
  2. Import NextResponse and getCurrentSession (KC-8.2).  
  3. Inside GET, call getCurrentSession.  
  4. If \!session?.user, return 401 Unauthorized NextResponse.  
  5. Return the session.user object directly (containing id, name, email populated by the session callback KC-8.1) with a 200 OK NextResponse. Do not query the database.  
  6. Include basic try/catch for unexpected errors, returning 500 status and logging errors (Security Doc Section 3.9).

13\. Ticket: KC-10.R: Refactor /api/auth/me to use NextAuth.js Session (Decision Made)

* Prompt: Verify the implementation of GET /api/auth/me (KC-10) correctly uses Option B (Session Data Only) as per the decision made for JIRA Ticket KC-10.R.  
  1. Review the code in app/api/auth/me/route.ts.  
  2. Confirm it uses getCurrentSession (KC-8.2).  
  3. Confirm it does not contain any calls to prisma.user.findUnique or other database queries.  
  4. Confirm it returns the session.user object directly in the 200 OK response.  
  5. Ensure the session callback (KC-8.1) reliably includes id, name, and email in the session object.  
  6. Update tests (KC-AUTH-TEST-BE-2) to verify this behavior (mocking getCurrentSession and asserting the response matches the mocked session user data without DB interaction).  
  * *Note: This approach prioritizes performance/simplicity for this endpoint but means the returned data might be slightly stale if the user's profile was updated elsewhere and the session hasn't refreshed.*

14\. Ticket: KC-12: Create API endpoint to update user profile data

* Prompt: Implement the API endpoint PUT /api/user/profile to allow authenticated users to update their profile name, as specified in JIRA Ticket KC-12, fulfilling PRD Requirement FR-AUTH-6.  
  1. Create app/api/user/profile/route.ts exporting an async PUT function.  
  2. Import NextResponse, prisma (KC-SETUP-8), getCurrentUserId (KC-8.2), and zod.  
  3. Define a Zod schema (UpdateProfileSchema) for the request body ({ name: z.string().min(1).max(255).optional() }). Allow name to be optional if only other fields might be updated later, or make required if it's the only updatable field for now. Adjust based on exact requirement. *Assuming name is the only field for now, make it required:* { name: z.string().min(1).max(255) }.  
  4. Inside PUT, call getCurrentUserId. Return 401 if null.  
  5. Parse and validate the request body using UpdateProfileSchema.safeParse. Return 400 on validation failure.  
  6. Use prisma.user.update({ where: { id: userId }, data: { name: validation.data.name }, select: { id: true, name: true, email: true } }) to update the user's name.  
  7. Return the updated user data with 200 status.  
  8. Include try/catch for database/server errors, returning 500 status and logging errors (Security Doc Section 3.9, Coding Standards Section 4.4).

15\. Ticket: KC-AUTH-FE-1: Create Reusable Auth Form Component

* Prompt: Implement the reusable AuthForm component at src/components/auth/AuthForm.tsx as specified in JIRA Ticket KC-AUTH-FE-1.  
  * Mark as a client component ('use client').  
  * Install and use react-hook-form and @hookform/resolvers/zod.  
  * Accept props: formType: 'login' | 'register', onSubmit: (data: any) \=\> Promise\<void\>, isLoading: boolean, apiError: string | null, title: string, submitButtonText: string.  
  * Use Chakra UI components (Box, VStack, Heading, FormControl, FormLabel, Input, Button, FormErrorMessage, Spinner, Alert, AlertIcon, InputGroup, InputRightElement for password visibility toggle) styled according to UI Style Guide and Figma Link from KC-AUTH-UX-1.  
  * Conditionally render the Name field based on formType \=== 'register'.  
  * Define Zod schemas for login (LoginSchema) and registration (RegisterSchema) (e.g., in src/lib/schemas/auth.ts).  
    * Crucially, ensure the RegisterSchema password validation aligns with the agreed policy: min 6, complexity rules (1 upper, 1 lower, 1 number, 1 special). Use .refine() or .regex().  
  * Use the appropriate schema with useForm({ resolver: zodResolver(...) }) based on formType.  
  * Integrate react-hook-form for state management and validation display (register, handleSubmit, formState: { errors, isSubmitting }).  
  * Display apiError prop using Alert when present.  
  * Handle isLoading prop on the submit button (set isDisabled={isLoading}, potentially show spinner within button).  
  * Ensure accessibility (labels, aria-invalid, focus management). Adhere to Coding Standards Section 5\.

16\. Ticket: KC-AUTH-FE-2: Implement Registration Page UI & Logic

* Prompt: Implement the Registration page at src/app/register/page.tsx as specified in JIRA Ticket KC-AUTH-FE-2.  
  * Mark as a client component ('use client').  
  * Use the reusable AuthForm component (KC-AUTH-FE-1) with formType='register', appropriate title, and button text.  
  * Visually match the design from the Registration Figma Link in KC-AUTH-UX-1, using Chakra layout components. Include link to Login page.  
  * Import useRouter from next/navigation and useToast from @chakra-ui/react.  
  * Implement the handleRegister async function passed to AuthForm's onSubmit:  
    * Set loading state (useState). Reset API error state.  
    * Call fetch('/api/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData) }) (KC-5).  
    * On success (response.ok): Show success useToast message (UI Style Guide) and redirect to /login using router.push('/login').  
    * On failure (\!response.ok): Parse error response JSON (if available, e.g., { message: 'Email already exists' } or Zod errors) and set API error state for AuthForm. Show generic error toast if parsing fails.  
    * Use try/catch for fetch errors.  
    * Manage loading state correctly (set back to false in finally block).  
  * Adhere to Coding Standards Section 5\.

17\. Ticket: KC-AUTH-FE-3: Implement Login Page UI & Logic

* Prompt: Implement the Login page at src/app/login/page.tsx as specified in JIRA Ticket KC-AUTH-FE-3.  
  * Mark as a client component ('use client').  
  * Use the reusable AuthForm component (KC-AUTH-FE-1) with formType='login', appropriate title, and button text.  
  * Visually match the design from the Login Figma Link in KC-AUTH-UX-1, using Chakra layout components. Include link to Register page.  
  * Import signIn from next-auth/react, useRouter and useSearchParams from next/navigation, useToast from @chakra-ui/react.  
  * Implement the handleLogin async function passed to AuthForm's onSubmit:  
    * Set loading state (useState). Reset API error state.  
    * Get the callbackUrl from useSearchParams (default to /dashboard).  
    * Call signIn('credentials', { redirect: false, email: formData.email, password: formData.password }) (KC-1.2).  
    * If result?.error: Map common errors (like 'CredentialsSignin') to user-friendly messages (e.g., "Invalid email or password") and set API error state for AuthForm. Show error toast.  
    * If result?.ok && \!result.error: Redirect to callbackUrl using router.push(callbackUrl).  
    * Handle unexpected errors during the signIn call.  
    * Manage loading state correctly (set back to false in finally block).  
  * Adhere to Coding Standards Section 5\.

18\. Ticket: KC-AUTH-FE-4: Implement Client-Side Session Handling

* Prompt: Implement client-side session handling mechanisms as specified in JIRA Ticket KC-AUTH-FE-4, fulfilling PRD Requirement FR-AUTH-5.  
  1. SessionProvider: Ensure SessionProvider from next-auth/react wraps the application in src/app/providers.tsx (KC-SETUP-3).  
  2. Header Component (src/components/layout/Header.tsx):  
     * Make it a client component ('use client').  
     * Use useSession() hook.  
     * Conditionally render Login/Register links (if status \=== 'unauthenticated') or Profile link/Logout button (if status \=== 'authenticated', using session.data.user.name or email).  
     * Handle status \=== 'loading' gracefully (e.g., show skeleton or null).  
     * Implement Logout button functionality using signOut() from next-auth/react.  
  3. AuthGuard Component (src/components/auth/AuthGuard.tsx):  
     * Create client component ('use client').  
     * Use useSession({ required: true, onUnauthenticated() { redirect('/login'); } }).  
     * If session.status \=== 'loading', render a loading indicator (e.g., full-page Chakra Spinner).  
     * If session.status \=== 'authenticated', render {children}.  
     * Return null otherwise (or during the brief period before redirect).  
  4. Protected Route Layout: Create a route group src/app/(protected)/ and its layout src/app/(protected)/layout.tsx. This layout component should simply wrap {children} with \<AuthGuard\>.  
  5. Ensure components follow Coding Standards Section 5 and UI Style Guide.

19\. Ticket: KC-AUTH-FE-5: Implement Basic Profile Page UI

* Prompt: Implement the basic Profile page UI at src/app/(protected)/profile/page.tsx as specified in JIRA Ticket KC-AUTH-FE-5, fulfilling PRD Requirement FR-AUTH-6.  
  * Place the page within the (protected) route group (KC-AUTH-FE-4). Mark as client component ('use client').  
  * Visually match the design from the Profile Figma Link in KC-AUTH-UX-1, using Chakra layout/text components (Heading, Text, VStack, Box, Button).  
  * Use useSession() hook from next-auth/react. Handle 'loading' state (should be handled by AuthGuard, but defensive check is okay).  
  * Display the authenticated user's name (session.data?.user?.name || 'N/A') and email (session.data?.user?.email).  
  * Include a Logout Button. On click, call signOut({ callbackUrl: '/' }) from next-auth/react.  
  * Ensure adherence to UI Style Guide and Coding Standards Section 5\.

20\. Ticket: KC-AUTH-FE-6: Implement Basic Profile Update UI

* Prompt: Enhance the Profile page (src/app/(protected)/profile/page.tsx from KC-AUTH-FE-5) to allow users to update their name, as specified in JIRA Ticket KC-AUTH-FE-6.  
  * Mark as client component ('use client'). Keep existing display elements.  
  * Add a form using react-hook-form and zodResolver for validation (name required, min 1, max 255). Use UpdateProfileSchema (similar to KC-12).  
  * Use useSession() hook, specifically destructuring the update function: const { data: session, status, update } \= useSession();.  
  * Pre-fill the name Input using useForm({ defaultValues: { name: session?.user?.name || '' } }). Use useEffect to reset form if session data loads after initial render.  
  * Implement the handleUpdateProfile async function for form submission:  
    * Set loading state (useState). Reset API error state (useState).  
    * Call fetch('/api/user/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: formData.name }) }) (KC-12).  
    * On success (response.ok): Show success useToast. Call await update({ name: formData.name }); to refresh the client-side session data automatically without a page reload. Reset form state if desired (reset({ name: formData.name })).  
    * On failure (\!response.ok): Parse error, set API error state. Show error useToast.  
    * Use try/catch for fetch errors.  
    * Manage loading state correctly (finally).  
  * Use Chakra UI components (FormControl, FormLabel, Input, Button, FormErrorMessage, Alert for API errors) according to UI Style Guide and Profile Figma Link. Adhere to Coding Standards Section 5\.

21\. Ticket: KC-72: Write Unit Tests for Authentication Logic

* Prompt: Write unit tests using Jest (KC-TEST-BE-1 setup) for the NextAuth.js callback functions defined in src/lib/auth.ts (KC-1.2, KC-8.1), as specified in JIRA Ticket KC-72.  
  * Create test file src/lib/auth.test.ts.  
  * Mock dependencies: Prisma Client (@/lib/prisma), Security Utils (@/lib/security), potentially next-auth itself if needed for complex scenarios.  
  * Test the authorize function (from CredentialsProvider):  
    * Mock prisma.user.findUnique and comparePassword.  
    * Test scenarios: valid credentials return user object, invalid email returns null, invalid password returns null, missing credentials return null. Assert the structure of the returned user object (id, name, email).  
  * Test the jwt callback:  
    * Verify it adds id, name, email to the token when the user object is present (initial sign-in).  
    * Verify it updates token fields when trigger \=== 'update' and session data is provided.  
  * Test the session callback: Verify it adds id, name, email to session.user based on the incoming token.  
  * Follow testing practices from Testing Strategy Section 2.1 and Coding Standards Section 4.5. Use jest.fn(), jest.mock(), beforeEach for mock resets.

22\. Ticket: KC-AUTH-TEST-FE-1: Write Unit Tests for Auth Form Component

* Prompt: Write unit tests using Jest and React Testing Library (KC-TEST-FE-1 setup) for the reusable AuthForm component (src/components/auth/AuthForm.tsx from KC-AUTH-FE-1), as specified in JIRA Ticket KC-AUTH-TEST-FE-1.  
  * Create test file src/components/auth/AuthForm.test.tsx.  
  * Use render (via test utility wrapper src/lib/test-utils.tsx), screen, userEvent.  
  * Test rendering for formType='login' vs 'register' (presence/absence of Name field).  
  * Test user input updates form values (await userEvent.type(...), expect(...).toHaveValue).  
  * Test client-side validation (required fields, email format, updated password policy validation: min 6 \+ complexity rules) triggers error messages (await userEvent.click(submitButton), expect(await screen.findByText(...)).toBeInTheDocument()).  
  * Test valid form submission calls the onSubmit mock prop with correct data (const onSubmitMock \= jest.fn(), await userEvent.click(submitButton), expect(onSubmitMock).toHaveBeenCalledWith(...)).  
  * Test isLoading prop disables button (expect(submitButton).toBeDisabled()).  
  * Test apiError prop displays error Alert (expect(screen.getByRole('alert')).toHaveTextContent(...)).  
  * Follow testing practices from Testing Strategy Section 2.1 and Coding Standards Section 5.4.

\--- NEW TESTING TICKETS \---

23\. Ticket: KC-AUTH-TEST-BE-1: Write Integration Tests for Registration API (/api/auth/register)

* Prompt: Write integration tests using Jest and potentially supertest or node-mocks-http (KC-TEST-BE-1 setup) for the POST /api/auth/register API endpoint (KC-5), as specified in JIRA Ticket KC-AUTH-TEST-BE-1.  
  * Create test file tests/integration/api/auth/register.test.ts (or similar structure).  
  * Mock Prisma Client (@/lib/prisma) to control database interactions.  
  * Test successful registration (201 Created): Mock findUnique (returns null), hashPassword, create (returns user). Send valid payload. Assert status code 201 and success message. Verify hashPassword and prisma.create were called correctly. Verify response does NOT contain session cookies.  
  * Test registration with existing email (409 Conflict): Mock findUnique (returns existing user). Send payload with existing email. Assert status code 409 and error message.  
  * Test registration with invalid payload (400 Bad Request): Send payload failing Zod validation (e.g., invalid email format, password too short based on updated policy). Assert status code 400 and presence of validation error details.  
  * Test database error during creation (500 Internal Server Error): Mock prisma.create to throw an error. Send valid payload. Assert status code 500\.  
  * Follow testing practices from Testing Strategy Section 2.2 and Coding Standards Section 4.5. Reset mocks between tests.

24\. Ticket: KC-AUTH-TEST-BE-2: Write Integration Tests for Get Profile API (/api/auth/me)

* Prompt: Write integration tests using Jest and potentially supertest or node-mocks-http (KC-TEST-BE-1 setup) for the GET /api/auth/me API endpoint (KC-10, implementing Option B), as specified in JIRA Ticket KC-AUTH-TEST-BE-2.  
  * Create test file tests/integration/api/auth/me.test.ts.  
  * Mock getServerSession from next-auth/next (or the helper getCurrentSession from KC-8.2).  
  * Test successful fetch (200 OK): Mock getCurrentSession to return a valid session object (with user: { id, name, email }). Make GET request. Assert status code 200 and that the response body matches the mocked session.user. Verify no database calls were made.  
  * Test unauthenticated access (401 Unauthorized): Mock getCurrentSession to return null. Make GET request. Assert status code 401\.  
  * Follow testing practices from Testing Strategy Section 2.2 and Coding Standards Section 4.5. Reset mocks between tests.

25\. Ticket: KC-AUTH-TEST-BE-3: Write Integration Tests for Update Profile API (/api/user/profile)

* Prompt: Write integration tests using Jest and potentially supertest or node-mocks-http (KC-TEST-BE-1 setup) for the PUT /api/user/profile API endpoint (KC-12), as specified in JIRA Ticket KC-AUTH-TEST-BE-3.  
  * Create test file tests/integration/api/user/profile.test.ts.  
  * Mock Prisma Client (@/lib/prisma) and getCurrentUserId (KC-8.2).  
  * Test successful update (200 OK): Mock getCurrentUserId (returns valid userId). Mock prisma.user.update (returns updated user data). Send valid payload ({ name: 'New Name' }). Assert status code 200 and response body matches mocked updated user. Verify prisma.update called with correct userId and data.  
  * Test update with invalid payload (400 Bad Request): Mock getCurrentUserId (returns valid userId). Send payload failing Zod validation (e.g., empty name). Assert status code 400\.  
  * Test unauthenticated access (401 Unauthorized): Mock getCurrentUserId (returns null). Make PUT request. Assert status code 401\.  
  * Test database error during update (500 Internal Server Error): Mock getCurrentUserId (returns valid userId). Mock prisma.user.update to throw an error. Send valid payload. Assert status code 500\.  
  * Follow testing practices from Testing Strategy Section 2.2 and Coding Standards Section 4.5. Reset mocks between tests.

26\. Ticket: KC-AUTH-TEST-FE-2: Write Integration Tests for Registration Page

* Prompt: Write integration tests using Jest and React Testing Library (KC-TEST-FE-1 setup) for the Registration Page (src/app/register/page.tsx from KC-AUTH-FE-2), as specified in JIRA Ticket KC-AUTH-TEST-FE-2.  
  * Create test file tests/integration/pages/RegisterPage.test.tsx.  
  * Mock next/navigation (useRouter, useSearchParams), @chakra-ui/react (useToast), and fetch.  
  * Test successful registration flow:  
    * Render the page within necessary providers (ChakraProvider, mock SessionProvider if needed).  
    * Fill out the form fields with valid data (matching updated password policy).  
    * Mock fetch for POST /api/auth/register to return a successful response (status 201, { ok: true }).  
    * Click the submit button.  
    * Assert fetch was called with the correct URL, method, headers, and body.  
    * Assert useToast was called with success parameters.  
    * Assert router.push was called with /login.  
  * Test registration failure (e.g., email exists):  
    * Fill out the form.  
    * Mock fetch to return an error response (status 409, { ok: false, status: 409, json: async () \=\> ({ message: 'Email already exists' }) }).  
    * Click submit.  
    * Assert fetch was called.  
    * Assert an API error message is displayed within the AuthForm component (e.g., screen.getByRole('alert')).  
    * Assert router.push was *not* called.  
  * Test client-side validation failure (handled mostly by KC-AUTH-TEST-FE-1, but can add a basic check here).  
  * Follow testing practices from Testing Strategy Section 2.2 and Coding Standards Section 5.4.

27\. Ticket: KC-AUTH-TEST-FE-3: Write Integration Tests for Login Page

* Prompt: Write integration tests using Jest and React Testing Library (KC-TEST-FE-1 setup) for the Login Page (src/app/login/page.tsx from KC-AUTH-FE-3), as specified in JIRA Ticket KC-AUTH-TEST-FE-3.  
  * Create test file tests/integration/pages/LoginPage.test.tsx.  
  * Mock next/navigation (useRouter, useSearchParams), @chakra-ui/react (useToast), and next-auth/react (signIn).  
  * Test successful login flow:  
    * Mock useSearchParams to return a specific callbackUrl or null.  
    * Render the page within necessary providers.  
    * Fill out email and password.  
    * Mock signIn to return a successful result ({ ok: true, error: null }).  
    * Click submit.  
    * Assert signIn was called with 'credentials' and the correct payload (email, password, redirect: false).  
    * Assert router.push was called with the expected callbackUrl (or default /dashboard).  
  * Test login failure (invalid credentials):  
    * Fill out the form.  
    * Mock signIn to return an error result ({ ok: false, error: 'CredentialsSignin' }).  
    * Click submit.  
    * Assert signIn was called.  
    * Assert an API error message ("Invalid email or password") is displayed within the AuthForm.  
    * Assert router.push was *not* called.  
  * Follow testing practices from Testing Strategy Section 2.2 and Coding Standards Section 5.4.

28\. Ticket: KC-AUTH-TEST-FE-4: Write Integration Tests for Profile Page (View & Update)

* Prompt: Write integration tests using Jest and React Testing Library (KC-TEST-FE-1 setup) for the Profile Page (src/app/(protected)/profile/page.tsx from KC-AUTH-FE-5 & KC-AUTH-FE-6), as specified in JIRA Ticket KC-AUTH-TEST-FE-4.  
  * Create test file tests/integration/pages/ProfilePage.test.tsx.  
  * Mock next-auth/react (useSession, signOut), fetch, @chakra-ui/react (useToast).  
  * Setup: Render the page within providers, mocking useSession to return an authenticated session (status: 'authenticated', data: { user: { name: 'Test User', email: 'test@example.com', id: '123' } }, update: jest.fn() }).  
  * Test initial display: Assert user name and email are displayed correctly.  
  * Test profile update success:  
    * Fill in the new name in the input field.  
    * Mock fetch for PUT /api/user/profile to return success (status 200, { ok: true, json: async () \=\> ({ name: 'New Name', ... }) }).  
    * Click the update button.  
    * Assert fetch was called correctly.  
    * Assert the update function (mocked from useSession) was called with { name: 'New Name' }.  
    * Assert success useToast was called.  
    * *(Optional: Assert form input value reflects the new name if form is reset)*  
  * Test profile update failure:  
    * Fill in the new name.  
    * Mock fetch to return an error (status 400, { ok: false, status: 400, json: async () \=\> ({ message: 'Validation error' }) }).  
    * Click update.  
    * Assert fetch was called.  
    * Assert an API error message is displayed.  
    * Assert the update function was *not* called.  
  * Test logout button:  
    * Mock signOut.  
    * Click the logout button.  
    * Assert signOut was called with { callbackUrl: '/' }.  
  * Follow testing practices from Testing Strategy Section 2.2 and Coding Standards Section 5.4.

29\. Ticket: KC-AUTH-TEST-FE-5: Write Unit Tests for AuthGuard and Header Components

* Prompt: Write unit tests using Jest and React Testing Library (KC-TEST-FE-1 setup) for the AuthGuard (KC-AUTH-FE-4) and Header (KC-AUTH-FE-4) components, as specified in JIRA Ticket KC-AUTH-TEST-FE-5.  
  * Create test files src/components/auth/AuthGuard.test.tsx and src/components/layout/Header.test.tsx.  
  * Mock next-auth/react (useSession) and next/navigation (redirect).  
  * AuthGuard Tests:  
    * Test loading state: Mock useSession (status: 'loading'). Render \<AuthGuard\>\<Child /\>\</AuthGuard\>. Assert loading indicator is shown and \<Child /\> is not.  
    * Test authenticated state: Mock useSession (status: 'authenticated'). Render. Assert \<Child /\> is rendered.  
    * Test unauthenticated state: Mock useSession (status: 'unauthenticated'). Render. Assert redirect('/login') was called. Assert \<Child /\> is not rendered.  
  * Header Tests:  
    * Test loading state: Mock useSession (status: 'loading'). Render \<Header /\>. Assert loading state UI (or null) is rendered.  
    * Test unauthenticated state: Mock useSession (status: 'unauthenticated'). Render. Assert Login and Register links are present. Assert Profile/Logout are *not* present.  
    * Test authenticated state: Mock useSession (status: 'authenticated', data: { user: { name: 'Test' } }). Render. Assert Profile link (with name/email) and Logout button are present. Assert Login/Register are *not* present.  
    * Test logout button click (within authenticated state test): Mock signOut. Click logout button. Assert signOut was called.  
  * Follow testing practices from Testing Strategy Section 2.1 and Coding Standards Section 5.4.