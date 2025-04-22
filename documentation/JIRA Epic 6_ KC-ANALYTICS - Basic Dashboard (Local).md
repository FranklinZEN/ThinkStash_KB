## **JIRA Epic: KC-ANALYTICS \- Basic Dashboard (Stage 1\)**

**Rationale:** Provide simple usage statistics based on local data to give users insights into their knowledge base size.

Ticket ID: KC-ANALYTICS-UX-1  
Title: Design Basic Dashboard UI  
Epic: KC-ANALYTICS  
PRD Requirement(s): FR-ANALYTICS-1  
Team: UX  
Dependencies (Functional): KC-SETUP-3 (Chakra UI)  
UX/UI Design Link: \[Link to Figma/mockups\]  
Description (Functional): Design the user interface for a simple dashboard page displaying key statistics about the user's knowledge cards, tags, and folders.  
Acceptance Criteria (Functional):

* Mockups show the layout of the dashboard page (e.g., using cards or a grid).  
* Designs specify which metrics are displayed (e.g., Total Cards, Total Tags, Total Folders).  
* Mockups detail the visual appearance of the components used to display these stats (e.g., "Stats Cards").  
* Designs specify handling of loading state while stats are being fetched.  
* Designs specify appearance when counts are zero.  
* Designs are responsive and include detailed specs.  
  Technical Approach / Implementation Notes:  
* Define layout structure (e.g., Chakra UI SimpleGrid for stat cards).  
* Specify appearance of individual stat cards (icon, label, value).  
* Ensure clear typography and visual hierarchy.  
* Consider accessibility for displaying numerical data and labels.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved: N/A (Design artifact)  
  Testing Considerations (Technical): Usability testing on prototypes. Accessibility review.  
  Dependencies (Technical): KC-SETUP-3

Ticket ID: KC-ANALYTICS-DA-1  
Title: Define Key Metrics for Basic Dashboard  
Epic: KC-ANALYTICS  
PRD Requirement(s): FR-ANALYTICS-1  
Team: DA/PM  
Dependencies (Functional): N/A  
UX/UI Design Link: N/A  
Description (Functional): Identify the core statistics to be displayed on the Stage 1 dashboard based on available local data.  
Acceptance Criteria (Functional):

* A defined list of metrics for the dashboard exists.  
* Metrics for Stage 1 are confirmed as: Total Card Count, Total Tag Count (used by the user), Total Folder Count.  
  Technical Approach / Implementation Notes:  
* Confirm metrics align with easily queryable data via Prisma based on existing schemas (User, Card, Tag, Folder).  
* Total Cards: count on Card table filtered by userId.  
* Total Tags: count on Tag table filtered by tags associated with cards owned by the userId.  
* Total Folders: count on Folder table filtered by userId.  
  API Contract (if applicable): N/A (Defines requirements for KC-61)  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved: N/A (Requirements definition)  
  Testing Considerations (Technical): N/A  
  Dependencies (Technical): N/A

Ticket ID: KC-61  
Title: Create API endpoint for Basic Stats  
Epic: KC-ANALYTICS  
PRD Requirement(s): FR-ANALYTICS-1  
Team: BE  
Dependencies (Functional): KC-ANALYTICS-DA-1 (Metrics defined), KC-8.2 (Auth Check), Relevant Schemas (Card, Tag, Folder)  
UX/UI Design Link: N/A  
Description (Functional): Implement the backend logic to calculate and return the basic statistics (total cards, tags, folders) for the logged-in user.  
Acceptance Criteria (Functional):

* Sending a GET request to /api/analytics/stats returns an object containing cardCount, tagCount, and folderCount for the logged-in user.  
* Counts accurately reflect the user's data in the database.  
* Returns 401 Unauthorized if the user is not logged in.  
  Technical Approach / Implementation Notes:  
* Create app/api/analytics/stats/route.ts. Export async function GET(request: Request).  
* Import NextResponse, prisma, getCurrentUserId.  
* const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
* Use try/catch.  
* Execute Prisma count queries within a transaction for consistency (optional but good practice):  
  const \[cardCount, tagCount, folderCount\] \= await prisma.$transaction(\[  
    prisma.card.count({  
      where: { userId: userId }  
    }),  
    // Count tags associated with the user's cards  
    prisma.tag.count({  
      where: {  
        cards: { some: { userId: userId } }  
      }  
    }),  
    prisma.folder.count({  
      where: { userId: userId }  
    })  
  \]);

  const stats \= {  
    cardCount,  
    tagCount,  
    folderCount  
  };

  return NextResponse.json(stats);

* Handle Prisma errors (500).  
  API Contract (if applicable):  
* **Endpoint:** GET /api/analytics/stats  
* **Request:** Auth via session.  
* **Response Success (200):** { cardCount: number, tagCount: number, folderCount: number }  
* **Response Error (401):** { error: 'Unauthorized' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* app/api/analytics/stats/route.ts  
* lib/sessionUtils.ts, lib/prisma.ts  
* Prisma count aggregations.  
  Testing Considerations (Technical): Test API response with user having data (cards, tags, folders), user with no data (all counts zero). Test auth requirement (401). Test database error handling (500). Verify counts are accurate based on seeded test data.  
  Dependencies (Technical): KC-ANALYTICS-DA-1, KC-8.2, KC-20.1-BLOCK, KC-20.2, KC-40

Ticket ID: KC-ANALYTICS-FE-2  
Title: Implement Reusable Stats Card Component  
Epic: KC-ANALYTICS  
PRD Requirement(s): FR-ANALYTICS-1  
Team: FE  
Dependencies (Functional): KC-ANALYTICS-UX-1 (Design), KC-SETUP-3 (Chakra UI)  
UX/UI Design Link: \[Link to Figma/mockups for Stats Card\]  
Description (Functional): Create a reusable React component to display a single statistic (e.g., "Total Cards") with its value and potentially an icon.  
Acceptance Criteria (Functional):

* Component accepts props for label (string), value (number or string), and optionally icon.  
* Renders the label, value, and icon according to the design.  
* Handles loading state (e.g., showing a skeleton or placeholder).  
* Matches the visual design from KC-ANALYTICS-UX-1.  
  Technical Approach / Implementation Notes:  
* Create src/components/analytics/StatsCard.tsx. Mark as 'use client' if using client-side hooks/icons, otherwise can be server component if data passed down.  
* Import Chakra UI components (Box, Stat, StatLabel, StatNumber, StatHelpText, StatArrow, Icon, Flex, SkeletonText).  
* Define props: interface StatsCardProps { label: string; value: number | string | undefined; icon?: React.ElementType; isLoading?: boolean; }.  
* Render Chakra Stat component within a styled Box (e.g., with padding, border, shadow).  
* Use StatLabel for props.label.  
* Use StatNumber for props.value. Handle undefined value during loading.  
* Conditionally render props.icon using Chakra Icon component, potentially within a Flex container.  
* If props.isLoading is true, render SkeletonText for label and number instead of actual values.  
  API Contract (if applicable): N/A (UI Component)  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/components/analytics/StatsCard.tsx  
* Chakra UI components (Stat, SkeletonText, Icon, etc.)  
* React Icons library (if used for icons, e.g., react-icons)  
  Testing Considerations (Technical): Unit test component rendering with different props (label, value, icon, isLoading). Verify loading state shows skeletons.  
  Dependencies (Technical): KC-ANALYTICS-UX-1, KC-SETUP-3

Ticket ID: KC-ANALYTICS-FE-1  
Title: Implement Dashboard Page Layout  
Epic: KC-ANALYTICS  
PRD Requirement(s): FR-ANALYTICS-1  
Team: FE  
Dependencies (Functional): KC-ANALYTICS-UX-1 (Design), KC-AUTH-FE-4 (AuthGuard)  
UX/UI Design Link: \[Link to Figma/mockups for Dashboard Page\]  
Description (Functional): Create the basic structure and layout for the dashboard page where analytics components will be placed.  
Acceptance Criteria (Functional):

* A dashboard page is accessible (e.g., at /dashboard) only to logged-in users.  
* Page has a clear title (e.g., "Dashboard").  
* Page uses the layout structure defined in the UX design (e.g., Chakra UI SimpleGrid) to arrange stats cards.  
* Placeholder areas or loading states are shown where stats cards will be integrated.  
  Technical Approach / Implementation Notes:  
* Use existing /dashboard page route (src/app/(protected)/dashboard/page.tsx) or create a new dedicated route if preferred. Ensure it's within the protected route group.  
* Import Chakra UI components (Box, Heading, SimpleGrid, Skeleton).  
* Set up the main page structure (Box with padding).  
* Add a Heading for the page title.  
* Use SimpleGrid component with appropriate columns (minChildWidth or columns) to define the layout for stats cards as per design.  
* Initially, render placeholder Skeleton components within the SimpleGrid cells where StatsCard components will go.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/app/(protected)/dashboard/page.tsx (or similar)  
* Chakra UI components (SimpleGrid, Heading, Skeleton)  
  Testing Considerations (Technical): Unit test page layout structure (verify title, SimpleGrid presence, initial skeletons). E2E test page accessibility for logged-in users.  
  Dependencies (Technical): KC-ANALYTICS-UX-1, KC-AUTH-FE-4

Ticket ID: KC-ANALYTICS-FE-3  
Title: Integrate API Data into Dashboard UI  
Epic: KC-ANALYTICS  
PRD Requirement(s): FR-ANALYTICS-1  
Team: FE  
Dependencies (Functional): KC-61 (Stats API), KC-ANALYTICS-FE-1 (Layout), KC-ANALYTICS-FE-2 (StatsCard Comp)  
UX/UI Design Link: N/A  
Description (Functional): Fetch the basic statistics from the API and display them on the dashboard page using the reusable Stats Card components.  
Acceptance Criteria (Functional):

* The dashboard page fetches data from GET /api/analytics/stats on load.  
* Loading state is handled correctly (showing skeletons or placeholders via StatsCard's isLoading prop).  
* Fetched statistics (cardCount, tagCount, folderCount) are displayed using StatsCard components.  
* API errors during fetching are handled gracefully (e.g., showing an error message).  
  Technical Approach / Implementation Notes:  
* Modify the dashboard page component (src/app/(protected)/dashboard/page.tsx). Mark as 'use client'.  
* Import useEffect, useState, StatsCard.  
* **Data Fetching:**  
  * Use useState for stats: StatsData | null, isLoading: boolean, error: string | null. (Define StatsData type based on API response).  
  * Use useEffect to fetch data from /api/analytics/stats.  
  * Set isLoading(true). Call fetch.  
  * On success: Parse JSON, setStats(data), setIsLoading(false).  
  * On failure: setError('Failed to load stats'), setIsLoading(false).  
  * **Alternative:** Use a data fetching library like SWR or React Query for caching, revalidation, etc. (Recommended for robustness, but basic fetch is okay for Stage 1).  
    * Example with SWR: import useSWR from 'swr'; const fetcher \= url \=\> fetch(url).then(res \=\> res.json()); const { data: stats, error, isLoading } \= useSWR('/api/analytics/stats', fetcher);  
* **Rendering:**  
  * Replace the placeholder Skeleton components in the SimpleGrid (from KC-ANALYTICS-FE-1).  
  * Render StatsCard components, passing the fetched data and loading state:  
    \<SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}\>  
      \<StatsCard label="Total Cards" value={stats?.cardCount} isLoading={isLoading} icon={/\* Optional Icon \*/} /\>  
      \<StatsCard label="Total Tags" value={stats?.tagCount} isLoading={isLoading} icon={/\* Optional Icon \*/} /\>  
      \<StatsCard label="Total Folders" value={stats?.folderCount} isLoading={isLoading} icon={/\* Optional Icon \*/} /\>  
    \</SimpleGrid\>

  * Display a general error message if error state is set.  
    API Contract (if applicable): Consumes GET /api/analytics/stats (KC-61).  
    Data Model Changes (if applicable): N/A  
    Key Functions/Modules Involved:  
* src/app/(protected)/dashboard/page.tsx  
* src/components/analytics/StatsCard.tsx  
* React useState, useEffect, fetch (or SWR/React Query)  
  Testing Considerations (Technical): Unit test data fetching logic (mock fetch or SWR). Test rendering of StatsCard components with fetched data and loading/error states. E2E test dashboard displays correct stats.  
  Dependencies (Technical): KC-61, KC-ANALYTICS-FE-1, KC-ANALYTICS-FE-2

Ticket ID: KC-ANALYTICS-TEST-BE-1 (Generated)  
Title: Write Unit Tests for Stats API Logic  
Epic: KC-ANALYTICS  
PRD Requirement(s): NFR-MAINT-1  
Team: BE/QA  
Dependencies (Functional): KC-61 (Stats API), KC-72 (Auth Test Setup)  
UX/UI Design Link: N/A  
Description (Functional): Create automated unit tests for the backend statistics API endpoint.  
Acceptance Criteria (Functional):

* Tests verify the API returns correct counts for cards, tags, and folders based on mocked Prisma responses.  
* Tests verify the counts are correctly scoped to the authenticated user.  
* Tests verify handling of users with no data (zero counts).  
* Tests verify authentication requirement (401).  
* Tests cover database error handling (500).  
  Technical Approach / Implementation Notes:  
* Use Jest/Vitest. Create test file src/app/api/analytics/stats/route.test.ts.  
* **Mock Dependencies:** Mock Prisma Client (prisma.card.count, prisma.tag.count, prisma.folder.count, prisma.$transaction), mock getCurrentUserId.  
* **Test GET /api/analytics/stats:**  
  * Mock getCurrentUserId (return userId).  
  * Mock the Prisma count calls (or the $transaction call) to return specific numbers.  
  * Test case: User with data. Assert 200 status and response body matches mocked counts ({ cardCount: ..., tagCount: ..., folderCount: ... }). Verify where clauses in mocked calls include the correct userId.  
  * Test case: User with no data. Mock counts return 0\. Assert 200 status and zero counts in response.  
  * Test auth failure (mock getCurrentUserId returns null, assert 401).  
  * Test Prisma error (mock count/transaction throws error, assert 500).  
    API Contract (if applicable): N/A  
    Data Model Changes (if applicable): N/A  
    Key Functions/Modules Involved:  
* app/api/analytics/stats/route.ts  
* Jest/Vitest, mocks.  
  Testing Considerations (Technical): Ensure mocks accurately reflect the arguments passed to Prisma functions (especially the where clauses for user scoping and tag relation).  
  Dependencies (Technical): KC-61, Testing framework setup.

Ticket ID: KC-ANALYTICS-TEST-FE-1 (Generated)  
Title: Write Unit Tests for Dashboard UI Components  
Epic: KC-ANALYTICS  
PRD Requirement(s): NFR-MAINT-1  
Team: FE/QA  
Dependencies (Functional): KC-ANALYTICS-FE-1 (Layout), KC-ANALYTICS-FE-2 (StatsCard Comp), KC-ANALYTICS-FE-3 (Data Integration), KC-TEST-FE-1  
UX/UI Design Link: N/A  
Description (Functional): Create automated unit tests for the frontend dashboard components.
Acceptance Criteria (Functional):
* Unit tests exist for StatsCard component (rendering props, loading state).
* Unit tests exist for the Dashboard page (mocking API call, rendering loading/error/success states, passing correct props to StatsCard).
Technical Approach / Implementation Notes:
* Use Jest/Vitest and React Testing Library.
* **StatsCard Tests:** Render with different props (label, value, icon, isLoading). Assert rendered output. Test `isLoading` prop renders SkeletonText.
* **Dashboard Page Tests:** Mock `fetch` (or SWR hook). Test loading state (assert `StatsCard` receives `isLoading={true}`). Test success state (assert `StatsCard` receives `isLoading={false}` and correct `value` props based on mocked data). Test error state (assert error message displayed).
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `src/components/analytics/StatsCard.tsx`, `src/app/(protected)/dashboard/page.tsx`, Jest/Vitest, RTL, mocks.
Testing Considerations (Technical): Mock data fetching effectively to test different UI states.
Dependencies (Technical): KC-ANALYTICS-FE-1, KC-ANALYTICS-FE-2, KC-ANALYTICS-FE-3, KC-TEST-FE-1