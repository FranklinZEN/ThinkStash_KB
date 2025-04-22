## **Additional Stage 1 Tickets (Based on Feedback)**

This document details the additional JIRA-style tickets recommended for Stage 1 based on feedback received, aiming to improve session handling, data portability, user experience, and documentation.

### **Authentication Enhancement (KC-AUTH)**

Ticket ID: KC-AUTH-FE-7  
Title: Handle Session Expiry UI Gracefully  
Epic: KC-AUTH  
PRD Requirement(s): Implied by FR-AUTH-5 (Robust Session Handling)  
Team: FE  
Dependencies (Functional): KC-AUTH-FE-4 (AuthGuard, useSession setup)  
UX/UI Design Link: N/A (Standard redirect/toast pattern likely sufficient)  
Description (Functional): Ensure the user interface provides clear feedback when a user's session expires or becomes invalid, guiding them back to the login page smoothly.  
Acceptance Criteria (Functional):

* When an API call fails specifically due to an expired/invalid session (e.g., returns 401), the user sees an informative message (e.g., Toast: "Your session has expired. Please log in again.").  
* When useSession status becomes unauthenticated after being authenticated, the user is redirected to the login page (handled by AuthGuard).  
* The experience avoids confusing errors when session expiry is the root cause.  
  Technical Approach / Implementation Notes:  
* **API Error Handling:** Modify global fetch wrapper or individual API call handlers in the frontend. If a 401 Unauthorized status is received, check if the user was previously authenticated (session.status \=== 'authenticated'). If so, trigger signOut({ redirect: false }) to clear the local session state and then show a specific "Session Expired" toast message before potentially redirecting via router.push('/login').  
* **AuthGuard:** The existing AuthGuard using useSession({ required: true }) already handles redirecting if the initial status is unauthenticated. This ticket focuses on handling expiry *during* an active session.  
* Toast Notification: Use Chakra UI useToast to display the expiry message clearly.  
  API Contract (if applicable): Relies on backend APIs consistently returning 401 for invalid/expired sessions (as implemented in KC-8.2).  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Frontend API call handling logic (e.g., utility fetch function, SWR/React Query error handlers).  
* useSession, signOut from next-auth/react.  
* useToast from @chakra-ui/react.  
* useRouter from next/navigation.  
  Testing Considerations (Technical): Difficult to unit test exact expiry, but test API error handling logic (mock fetch returning 401). Manually test by setting a very short session maxAge locally (lib/auth.ts) and waiting for expiry or by manually deleting the session cookie in browser dev tools.  
  Dependencies (Technical): KC-AUTH-FE-4

### **Data Portability (New Epic Suggestion: KC-DATA)**

Ticket ID: KC-DATA-EXPORT-BE-1  
Title: Implement JSON Export API Logic  
Epic: KC-DATA (New) / KC-CARD-CREATE  
PRD Requirement(s): Implied by Manual Migration Strategy (Stage 1 \-\> 2\)  
Team: BE  
Dependencies (Functional): KC-8.2 (Auth Check), Schemas (User, Card, Tag, Folder)  
UX/UI Design Link: N/A  
Description (Functional): Create a backend endpoint that allows a logged-in user to export all their data (cards, tags, folder structure) as a structured JSON file.  
Acceptance Criteria (Functional):

* Sending a GET request to /api/export by an authenticated user triggers the data export process.  
* The API fetches all cards (with content and tags), all folders, and all relevant tags associated with the user.  
* The API structures this data into a single JSON object, preserving folder hierarchy and card-tag relationships.  
* The API returns the JSON data, prompting a file download for the user.  
* Returns 401 if the user is not logged in.  
* Handles potential errors during data fetching.  
  Technical Approach / Implementation Notes:  
* Create app/api/export/route.ts. Export async function GET(request: Request).  
* Import NextResponse, prisma, getCurrentUserId.  
* const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
* Use try/catch.  
* Fetch all necessary data for the user:  
  const folders \= await prisma.folder.findMany({ where: { userId }, orderBy: { name: 'asc' } });  
  const cards \= await prisma.card.findMany({ where: { userId }, include: { tags: { select: { name: true } } }, orderBy: { updatedAt: 'desc' } });  
  // Note: Tags are included with cards. Fetching all unique tags separately might also be useful.

* Structure the data into a JSON object. Preserve folder hierarchy (e.g., by nesting or providing parent IDs). Map tag names directly onto card objects.  
  const exportData \= {  
    schemaVersion: 1, // Versioning for future compatibility  
    exportedAt: new Date().toISOString(),  
    folders: folders, // Can be flat list, FE/importer reconstructs tree  
    cards: cards.map(card \=\> ({  
      ...card,  
      content: card.content, // Ensure content is included  
      tags: card.tags.map(tag \=\> tag.name) // Export tag names  
    })),  
  };

* Return the JSON data with appropriate headers for file download:  
  const jsonString \= JSON.stringify(exportData, null, 2); // Pretty print  
  const headers \= new Headers();  
  headers.set('Content-Type', 'application/json');  
  headers.set('Content-Disposition', \`attachment; filename="knowledge\_card\_export\_${new Date().toISOString().split('T')\[0\]}.json"\`);  
  return new NextResponse(jsonString, { status: 200, headers });

* Handle Prisma errors (500).  
  API Contract (if applicable):  
* **Endpoint:** GET /api/export  
* **Request:** Auth via session.  
* **Response Success (200):** JSON data payload with Content-Disposition: attachment.  
* **Response Error (401):** { error: 'Unauthorized' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* app/api/export/route.ts  
* lib/sessionUtils.ts, lib/prisma.ts  
* JSON structuring logic.  
  Testing Considerations (Technical): Test API response for users with data (nested folders, cards with/without tags) and users with no data. Verify downloaded file content and structure. Test auth (401). Test error handling.  
  Dependencies (Technical): KC-8.2, All relevant schemas (User, Card, Tag, Folder).

Ticket ID: KC-DATA-EXPORT-FE-1  
Title: Implement JSON Export UI  
Epic: KC-DATA (New) / KC-CARD-CREATE  
PRD Requirement(s): Implied by Manual Migration Strategy  
Team: FE  
Dependencies (Functional): KC-DATA-EXPORT-BE-1 (Export API)  
UX/UI Design Link: N/A (Simple button likely sufficient)  
Description (Functional): Provide a user interface element (e.g., a button in settings or profile page) for users to trigger the data export process.  
Acceptance Criteria (Functional):

* An "Export My Data" button or similar UI element is available (e.g., on the Profile page).  
* Clicking the button initiates a request to the GET /api/export endpoint.  
* The browser prompts the user to download the generated JSON file upon successful API response.  
* Loading state is indicated while the export is being generated.  
* Errors during the export process are communicated to the user (e.g., Toast).  
  Technical Approach / Implementation Notes:  
* Add an "Export Data" Button to a suitable page (e.g., src/app/(protected)/profile/page.tsx).  
* Import useState. Use useState for isLoading.  
* Implement handleExportData function:  
  const \[isLoading, setIsLoading\] \= useState(false);  
  const toast \= useToast(); // If using Chakra

  const handleExportData \= async () \=\> {  
    setIsLoading(true);  
    try {  
      const response \= await fetch('/api/export');  
      if (\!response.ok) {  
        throw new Error('Export failed');  
      }  
      // Browser handles download automatically due to Content-Disposition header  
      // Optionally, show success toast  
      toast({ title: 'Export started', description: 'Your download should begin shortly.', status: 'success' });  
    } catch (error) {  
      console.error("Export error:", error);  
      toast({ title: 'Export failed', description: 'Could not export your data.', status: 'error' });  
    } finally {  
      setIsLoading(false);  
    }  
  };

* Attach handleExportData to the button's onClick. Set isLoading prop on the button.  
  API Contract (if applicable): Consumes GET /api/export (KC-DATA-EXPORT-BE-1).  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Profile page component (or settings page).  
* Chakra UI Button, useToast.  
* React useState, fetch.  
  Testing Considerations (Technical): Unit test handleExportData logic (mock fetch, toast). E2E test clicking the button and verifying a download prompt appears (actual download verification is harder in automated E2E). Test loading and error states.  
  Dependencies (Technical): KC-DATA-EXPORT-BE-1

### **User Experience Enhancement (New Epic Suggestion: KC-ONBOARDING)**

Ticket ID: KC-UX-ONBOARD-1  
Title: Design Basic User Onboarding/Help Prompts  
Epic: KC-ONBOARDING (New) / KC-UX  
PRD Requirement(s): Implied usability NFR  
Team: UX  
Dependencies (Functional): Core features (Card Create, Folders, Search) exist.  
UX/UI Design Link: \[Link to Figma/mockups for Onboarding\]  
Description (Functional): Design a minimal onboarding experience or contextual help system to guide new users through the core functionalities of the Stage 1 application.  
Acceptance Criteria (Functional):

* Designs specify the onboarding flow (e.g., welcome modal, short feature tour, contextual tooltips).  
* Key features to highlight are identified (e.g., create card button, folder creation, search bar).  
* Mockups detail the appearance and content of onboarding elements (modals, tooltips, popovers).  
* Designs consider how users dismiss or skip onboarding.  
* Designs are consistent with the overall application style.  
  Technical Approach / Implementation Notes:  
* Choose onboarding pattern:  
  * **Welcome Modal:** Simple modal on first login explaining core concepts.  
  * **Feature Tour:** Step-by-step guide using tooltips/popovers pointing to key UI elements (e.g., using libraries like react-joyride or shepherd.js).  
  * **Contextual Tooltips:** Permanent or hover-triggered tooltips on specific elements.  
* Define trigger conditions (e.g., only for first login, resettable).  
* Write concise and helpful copy for onboarding messages.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): Might require adding a flag to the User model (hasCompletedOnboarding: Boolean?) if tracking completion state is needed beyond local storage.  
  Key Functions/Modules Involved: N/A (Design artifact)  
  Testing Considerations (Technical): Usability testing of the onboarding flow.  
  Dependencies (Technical): N/A

Ticket ID: KC-UX-ONBOARD-FE-1  
Title: Implement Basic User Onboarding/Help Prompts  
Epic: KC-ONBOARDING (New) / KC-UX  
PRD Requirement(s): Implied usability NFR  
Team: FE  
Dependencies (Functional): KC-UX-ONBOARD-1 (Design finalized), Core feature components.  
UX/UI Design Link: \[Link to Figma/mockups for Onboarding\]  
Description (Functional): Implement the designed minimal onboarding flow or contextual help elements in the frontend application.  
Acceptance Criteria (Functional):

* The chosen onboarding pattern (modal, tour, tooltips) is implemented according to the design.  
* Onboarding triggers under the specified conditions (e.g., first visit/login).  
* Users can dismiss or complete the onboarding flow.  
* (If applicable) Onboarding completion state is persisted (e.g., using localStorage or a user profile flag).  
  Technical Approach / Implementation Notes:  
* Based on the chosen pattern:  
  * **Modal:** Use Chakra UI Modal. Trigger based on a flag checked on login/app load. Store completion flag in localStorage.  
  * **Feature Tour:** Integrate a library like react-joyride. Define tour steps targeting specific DOM elements (using selectors). Trigger tour based on completion flag. Store completion flag.  
  * **Tooltips:** Use Chakra UI Tooltip or Popover components attached to relevant buttons/icons.  
* Manage onboarding state (e.g., showOnboarding, onboardingStep).  
* If persisting completion state on the backend is needed, update User schema (KC-3.1) and add an API endpoint to update the flag. For Stage 1 MVP, localStorage is likely sufficient.  
  API Contract (if applicable): Optional: API to update User.hasCompletedOnboarding flag.  
  Data Model Changes (if applicable): Optional: Add hasCompletedOnboarding to User schema.  
  Key Functions/Modules Involved:  
* Relevant UI components where onboarding elements appear.  
* Onboarding state management logic.  
* (If used) Onboarding library (react-joyride, etc.).  
* localStorage API.  
* Chakra UI components (Modal, Tooltip, Popover).  
  Testing Considerations (Technical): Unit test onboarding component logic (triggering, step navigation, completion). E2E test the onboarding flow for a new user. Test persistence of completion state.  
  Dependencies (Technical): KC-UX-ONBOARD-1

### **Documentation Enhancement**

Ticket ID: KC-DOCS-1  
Title: Document Core Data Schemas  
Epic: General / KC-SETUP  
PRD Requirement(s): NFR-MAINT-1 (Implied)  
Team: BE/Dev  
Dependencies (Functional): Schemas defined (User, Card, Tag, Folder)  
UX/UI Design Link: N/A  
Description (Functional): Create clear documentation outlining the structure of the core data models, particularly the Prisma schema and the expected JSON structure for the Card content field.  
Acceptance Criteria (Functional):

* A Markdown file (e.g., docs/schemas.md or within README.md) exists in the repository.  
* Documentation details the fields, types, relations, and key constraints for the User, Card, Tag, and Folder Prisma models.  
* Documentation explicitly describes the expected JSON structure stored in the Card.content field (based on BlockNote's PartialBlock\[\] structure), including examples of common block types (paragraph, heading, list).  
  Technical Approach / Implementation Notes:  
* Create the Markdown file.  
* Copy relevant sections from prisma/schema.prisma and add explanations for fields, relations (@relation), and constraints (@id, @unique, @default, @@index, @@unique). Explain onDelete behavior.  
* Provide a clear example of the BlockNote JSON structure for a simple card containing a heading, a paragraph with bold text, and a list. Reference BlockNote documentation if necessary but show the expected stored format.  
* Keep the documentation concise and focused on the essential structure for developers working on the codebase.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved: Markdown documentation file(s).  
  Testing Considerations (Technical): Review documentation for clarity and accuracy against the actual schema and BlockNote usage.  
  Dependencies (Technical): All schema definition tickets (KC-3.1, KC-20.1-BLOCK, KC-20.2, KC-40).