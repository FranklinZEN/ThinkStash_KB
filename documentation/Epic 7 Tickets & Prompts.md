# **Review and AI Prompts for Additional Stage 1 Tickets (Epic 7\)**

This document contains the technical review and AI development prompts for a collection of additional tickets recommended for Stage 1 based on feedback. These tickets aim to enhance session handling, data portability, user experience, and documentation.

## **Part 1: Tech Lead Review of Additional Stage 1 Tickets**

This set of tickets addresses feedback and gaps identified for Stage 1, focusing on improving robustness, usability, and maintainability rather than introducing a single large feature. They are grouped into functional areas: Authentication Enhancement, Data Portability, User Experience Enhancement, and Documentation.

**A. Scope and Purpose:**

* **Session Handling (KC-AUTH-FE-7):** Improves the user experience when sessions expire during active use, preventing confusing errors and guiding the user back to login.  
* **Data Portability (KC-DATA-EXPORT-\*):** Introduces a crucial JSON export feature. This is particularly important for enabling users to back up their data and potentially for manual data migration between development stages or environments if needed. Suggests a new mini-epic KC-DATA.  
* **User Experience (KC-UX-ONBOARD-\*):** Adds basic user onboarding or contextual help to guide new users, improving initial usability. Suggests a new mini-epic KC-ONBOARDING.  
* **Documentation (KC-DOCS-1):** Addresses the need for clear documentation of the core data schemas, aiding developer understanding and future maintenance.

**B. Key Technical Points & Considerations:**

* **Session Expiry Handling:** Requires careful modification of frontend API call handling to specifically detect 401 errors indicative of expiry (when already authenticated) and trigger a clean sign-out and informative message.  
* **JSON Export:** The backend API needs to fetch all relevant user data (folders, cards with tags) and structure it logically within a single JSON file. Setting correct Content-Disposition headers is key for triggering the browser download. The schema includes versioning, which is good practice.  
* **Onboarding:** Offers flexibility in implementation (modal, tour, tooltips). For Stage 1, using localStorage to track completion is likely sufficient, avoiding immediate schema changes. Integrating a library like react-joyride can simplify tour implementation but adds a dependency.  
* **Schema Documentation:** A straightforward task involving creating a Markdown file and clearly explaining the Prisma models and the expected BlockNote JSON structure in Card.content.

**C. Potential Gaps/Refinements:**

* **Export Scalability:** For users with vast amounts of data, fetching everything in a single request might become slow or memory-intensive. This is acceptable for Stage 1 but could require streaming or background job processing in the future.  
* **Onboarding Complexity:** Feature tours can become brittle if the UI changes frequently. A simpler modal or contextual tooltips might be more maintainable initially.  
* **Data Import:** This set of tickets only covers export. A corresponding import feature would be needed for true data migration but is outside the scope of Stage 1\.

**D. Overall:**

These tickets represent valuable additions to Stage 1, significantly improving the polish, practicality, and maintainability of the application. The data export feature, in particular, is strategically important.

## **Part 2: AI Development Prompts for Additional Stage 1 Tickets**

*(Prompts reference the full suite of project documents and incorporate review findings)*

**Authentication Enhancement (KC-AUTH)**

**1\. Ticket: KC-AUTH-FE-7: Handle Session Expiry UI Gracefully**

* **Prompt:** Enhance frontend API error handling to gracefully manage session expiry, as specified in **JIRA Ticket KC-AUTH-FE-7**.  
  1. Modify the global fetch wrapper or individual API call handlers.  
  2. Inside the error handling logic (e.g., catch block or error handler for useSWR/react-query):  
     * Check if the error corresponds to a 401 Unauthorized response (error.response?.status \=== 401 or similar).  
     * Check the current session status using useSession().  
     * **If** the status was previously 'authenticated' **and** a 401 is received, assume session expiry:  
       * Call signOut({ redirect: false, callbackUrl: '/login' }) to clear the local NextAuth state. *Note: signOut might automatically redirect if callbackUrl is provided, test behavior.*  
       * Display an informative toast using useToast: "Your session has expired. Please log in again."  
       * If signOut doesn't redirect automatically, use router.push('/login').  
  3. Ensure the AuthGuard (**KC-AUTH-FE-4**) remains in place to handle cases where the session is already invalid on initial load.  
  4. Write unit tests for the modified error handling logic, mocking fetch to return 401, mocking useSession, signOut, useToast, and useRouter to verify the correct sequence of actions. Manually test expiry behavior locally.

**Data Portability (New Epic Suggestion: KC-DATA)**

**2\. Ticket: KC-DATA-EXPORT-BE-1: Implement JSON Export API Logic**

* **Prompt:** Implement the GET /api/export endpoint to allow users to download their data, as specified in **JIRA Ticket KC-DATA-EXPORT-BE-1**.  
  1. Create app/api/export/route.ts. Export async GET(request: Request).  
  2. Import NextResponse, prisma, getCurrentUserId (**KC-8.2**).  
  3. Auth check: const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }.  
  4. Use try/catch.  
  5. Fetch all user data:  
     * const folders \= await prisma.folder.findMany({ where: { userId }, orderBy: { name: 'asc' } });  
     * const cards \= await prisma.card.findMany({ where: { userId }, include: { tags: { select: { name: true } } }, orderBy: { updatedAt: 'desc' } });  
  6. Structure the export data:  
     const exportData \= {  
       schemaVersion: 1,  
       exportedAt: new Date().toISOString(),  
       folders: folders, // Flat list is acceptable  
       cards: cards.map(card \=\> ({  
         id: card.id,  
         title: card.title,  
         content: card.content, // Ensure Prisma.JsonValue is serializable  
         createdAt: card.createdAt,  
         updatedAt: card.updatedAt,  
         folderId: card.folderId,  
         tags: card.tags.map(tag \=\> tag.name) // Array of tag names  
       })),  
     };

  7. Serialize and return JSON with download headers:  
     const jsonString \= JSON.stringify(exportData, null, 2);  
     const headers \= new Headers();  
     headers.set('Content-Type', 'application/json');  
     const timestamp \= new Date().toISOString().split('T')\[0\];  
     headers.set('Content-Disposition', \\\`attachment; filename="knowledge\_card\_export\_${timestamp}.json"\\\`);  
     return new NextResponse(jsonString, { status: 200, headers });

  8. Handle Prisma/other errors (500).  
  9. Write integration tests verifying the API response structure, headers, and content for users with and without data. Test auth (401) and error handling.

**3\. Ticket: KC-DATA-EXPORT-FE-1: Implement JSON Export UI**

* **Prompt:** Implement the frontend UI element to trigger the data export, as specified in **JIRA Ticket KC-DATA-EXPORT-FE-1**.  
  1. Choose a suitable location (e.g., Profile Page src/app/(protected)/profile/page.tsx).  
  2. Import useState, Button, useToast from Chakra UI.  
  3. Add state: const \[isLoading, setIsLoading\] \= useState(false);.  
  4. Add an "Export My Data" Button. Set its isLoading prop to the state variable. Attach onClick={handleExportData}.  
  5. Implement handleExportData \= async () \=\> { ... }:  
     * Set isLoading(true).  
     * Use try/catch around fetch('/api/export').  
     * If \!response.ok, throw an error.  
     * On success, show a toast: "Export started. Your download should begin shortly." (Browser handles download via headers).  
     * On error, show an error toast: "Export failed."  
     * Use finally to set isLoading(false).  
  6. Write unit tests mocking fetch and useToast, verifying loading state changes and toast messages on success/failure.

**User Experience Enhancement (New Epic Suggestion: KC-ONBOARDING)**

**4\. Ticket: KC-UX-ONBOARD-1: Design Basic User Onboarding/Help Prompts**

* **Prompt (For TL/Dev Reference):** Review and finalize the UX designs for a minimal user onboarding experience, as specified in **JIRA Ticket KC-UX-ONBOARD-1**.  
  * Choose an appropriate pattern (Welcome Modal, Feature Tour, Contextual Tooltips). Consider maintainability for Stage 1 (Modal or Tooltips might be simpler than a tour).  
  * Identify key UI elements/features to highlight (e.g., Create Card, Create Folder, Search).  
  * Design the visual appearance (modals, tooltips) and write clear, concise copy.  
  * Specify trigger conditions (e.g., first login) and dismiss/skip interactions.  
  * Ensure consistency with the **UI Style Guide**.  
  * These designs guide **KC-UX-ONBOARD-FE-1**.

**5\. Ticket: KC-UX-ONBOARD-FE-1: Implement Basic User Onboarding/Help Prompts**

* **Prompt:** Implement the chosen basic onboarding flow based on the design from **KC-UX-ONBOARD-1**, as specified in **JIRA Ticket KC-UX-ONBOARD-FE-1**.  
  1. **Choose Implementation Strategy:**  
     * **Modal:** Use Chakra UI Modal. Trigger on app load/login based on a flag in localStorage. Add a "Don't show again" checkbox that sets the flag.  
     * **Feature Tour:** Integrate react-joyride or similar. Define steps targeting DOM selectors. Trigger based on localStorage flag. Store completion flag.  
     * **Tooltips:** Use Chakra UI Tooltip or Popover on specific elements, potentially always visible or triggered contextually.  
  2. **State Management:** Use localStorage to store a flag like hasCompletedOnboarding. Check this flag on application load to determine if onboarding should be shown.  
     // Example check  
     useEffect(() \=\> {  
       const completed \= localStorage.getItem('hasCompletedOnboarding');  
       if (\!completed) {  
         // Trigger onboarding (e.g., open modal, start tour)  
       }  
     }, \[\]);

     // Example setting flag on completion/dismiss  
     const handleOnboardingComplete \= () \=\> {  
       localStorage.setItem('hasCompletedOnboarding', 'true');  
       // Close modal, stop tour, etc.  
     };

  3. Implement the UI elements (Modal content, Tour steps, Tooltip content) according to the design.  
  4. Ensure users can dismiss/complete the flow, triggering the state persistence (handleOnboardingComplete).  
  5. *(Optional \- Defer if possible)* If backend persistence is strictly required, coordinate with BE to add hasCompletedOnboarding: Boolean? to User schema (**KC-3.1**) and an API endpoint to update it.  
  6. Write unit tests for the onboarding components, mocking localStorage and testing trigger conditions, display logic, and completion/dismissal actions.

**Documentation Enhancement**

**6\. Ticket: KC-DOCS-1: Document Core Data Schemas**

* **Prompt:** Create Markdown documentation for the core data schemas, as specified in **JIRA Ticket KC-DOCS-1**.  
  1. Create a file (e.g., docs/schemas.md or add a section to README.md).  
  2. For each core model (User, Card, Tag, Folder):  
     * List fields with their types (from prisma/schema.prisma).  
     * Explain key relations (@relation) including field links and onDelete behavior (Cascade, SetNull).  
     * Explain constraints (@id, @unique, @@unique, @default, @@index).  
  3. **Card Content JSON:** Provide a clear example of the expected JSON structure stored in the Card.content field, based on BlockNote's PartialBlock\[\] format. Include examples for paragraph, heading, list, and text with marks (like bold).  
     \#\#\# Card Content JSON Structure (\`content\` field)

     Based on BlockNote's \`PartialBlock\[\]\` type. Example:

     \\\`\\\`\\\`json  
     \[  
       {  
         "id": "...",  
         "type": "heading",  
         "props": { "level": 1 },  
         "content": \[{ "type": "text", "text": "Example Title", "styles": {} }\]  
       },  
       {  
         "id": "...",  
         "type": "paragraph",  
         "content": \[  
           { "type": "text", "text": "This is ", "styles": {} },  
           { "type": "text", "text": "bold", "styles": { "bold": true } },  
           { "type": "text", "text": " text.", "styles": {} }  
         \]  
       },  
       {  
         "id": "...",  
         "type": "bulletListItem",  
         "content": \[{ "type": "text", "text": "List item 1", "styles": {} }\]  
       }  
     \]  
     \\\`\\\`\\\`

  4. Ensure the documentation is clear, accurate, and easy for developers to understand. Review against the actual schema.