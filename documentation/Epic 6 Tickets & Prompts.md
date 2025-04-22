# **Review and AI Prompts for KC-ANALYTICS Epic (Stage 1\)**

This document contains the technical review and AI development prompts for the KC-ANALYTICS epic (Stage 1), focusing on implementing a basic dashboard displaying simple usage statistics.

## **Part 1: Tech Lead Review of KC-ANALYTICS Epic (Stage 1\)**

This epic introduces a basic dashboard feature for Stage 1, providing users with simple insights into the size of their knowledge base by displaying counts of their cards, tags, and folders based on the locally stored data.

**A. Scope and Purpose:**

* **Goal:** To provide users with immediate, simple feedback on their usage and the scale of their knowledge base within the application.  
* **Functionality:** Covers the design of the dashboard UI, definition of the specific metrics to display (Card Count, Tag Count, Folder Count), a backend API endpoint to retrieve these counts, and frontend components to display them.  
* **Simplicity:** This epic focuses on fundamental counts derived directly from existing data models. More complex analytics or visualizations are deferred.

**B. Key Technical Points & Considerations:**

* **Backend API (KC-61):** A single, straightforward API endpoint (GET /api/analytics/stats) is sufficient. It uses Prisma count aggregations, potentially within a $transaction for consistency, to retrieve the necessary numbers efficiently. The tag count query correctly counts tags associated *only* with the user's cards.  
* **Frontend Implementation:**  
  * **Component Reusability (KC-ANALYTICS-FE-2):** Defines a reusable StatsCard component, promoting consistency in how statistics are displayed. This component includes handling for loading states.  
  * **Layout (KC-ANALYTICS-FE-1):** Uses standard layout components (e.g., Chakra UI SimpleGrid) to arrange the stats cards on the dashboard page.  
  * **Data Fetching (KC-ANALYTICS-FE-3):** Involves a simple client-side fetch (or potentially using SWR/React Query) to get the stats data and populate the StatsCard components, handling loading and error states.  
* **Dependencies:** Relies heavily on the previously defined schemas (Card, Tag, Folder \- **KC-20.1-BLOCK, KC-20.2, KC-40**), authentication checks (**KC-8.2**), and the base UI setup (**KC-SETUP-3**, **KC-AUTH-FE-4**).

**C. Potential Gaps/Refinements:**

* **Basic Metrics Only:** Stage 1 only includes total counts. Time-based analytics (e.g., cards created this week), tag/folder specific counts, or more complex metrics are not included.  
* **Local Data Limitation:** Statistics are based purely on the local database in Stage 1\.

**D. Overall:**

This is a well-defined and relatively simple epic that adds immediate value by giving users basic visibility into their data. It leverages existing infrastructure and focuses on clear presentation through reusable components.

## **Part 2: AI Development Prompts for KC-ANALYTICS Epic (Stage 1\)**

*(Prompts reference the full suite of project documents and incorporate review findings)*

**1\. Ticket: KC-ANALYTICS-UX-1: Design Basic Dashboard UI**

* **Prompt (For TL/Dev Reference):** Review and finalize the UX designs for the basic dashboard page, as specified in **JIRA Ticket KC-ANALYTICS-UX-1**. Ensure designs:  
  * Detail the layout for displaying statistics (e.g., using Chakra UI SimpleGrid or HStack with StatsCard components).  
  * Specify the visual appearance of the StatsCard component (icon, label, value).  
  * Cover loading states (skeletons) and zero-count states.  
  * Align with the overall **UI Style Guide** and **KC-SETUP-3 (Chakra UI)**.  
  * Include responsiveness and accessibility considerations.  
  * These designs guide **KC-ANALYTICS-FE-1** and **KC-ANALYTICS-FE-2**.

**2\. Ticket: KC-ANALYTICS-DA-1: Define Key Metrics for Basic Dashboard**

* **Prompt (For PM/Analyst Reference):** Confirm the key metrics for the Stage 1 dashboard, as specified in **JIRA Ticket KC-ANALYTICS-DA-1**.  
  * Verify the metrics are:  
    * Total Card Count (User's cards)  
    * Total Tag Count (Unique tags used on user's cards)  
    * Total Folder Count (User's folders)  
  * Ensure these align with user needs for basic insights and are directly derivable from the schemas defined in **KC-20.1-BLOCK, KC-20.2, KC-40**. These metrics define the data required from the API (**KC-61**).

**3\. Ticket: KC-61: Create API endpoint for Basic Stats**

* **Prompt:** Implement the GET /api/analytics/stats endpoint to return basic counts for the logged-in user, as specified in **JIRA Ticket KC-61**.  
  1. Create app/api/analytics/stats/route.ts. Export async GET(request: Request).  
  2. Import NextResponse, prisma, getCurrentUserId (**KC-8.2**).  
  3. Auth check: const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }.  
  4. Use try/catch.  
  5. Fetch counts using prisma.$transaction for atomicity:  
     const \[cardCount, tagCount, folderCount\] \= await prisma.$transaction(\[  
       prisma.card.count({ where: { userId: userId } }),  
       prisma.tag.count({ where: { cards: { some: { userId: userId } } } }), // Counts tags linked to user's cards  
       prisma.folder.count({ where: { userId: userId } })  
     \]);  
     const stats \= { cardCount, tagCount, folderCount };  
     return NextResponse.json(stats);

  6. Handle Prisma/other errors (500).  
  7. Define API Contract:  
     * Endpoint: GET /api/analytics/stats  
     * Response Success (200): { cardCount: number, tagCount: number, folderCount: number }  
     * Response Error (401): { error: 'Unauthorized' }  
     * Response Error (500): { error: 'Internal server error' }  
  8. Write unit tests (**KC-ANALYTICS-TEST-BE-1**) covering success (with/without data), auth error, DB error, verifying correct where clauses used in mocked counts.

**4\. Ticket: KC-ANALYTICS-FE-2: Implement Reusable Stats Card Component**

* **Prompt:** Create the reusable StatsCard component for displaying dashboard metrics, as specified in **JIRA Ticket KC-ANALYTICS-FE-2**.  
  1. Create src/components/analytics/StatsCard.tsx.  
  2. Import Chakra UI components (Box, Stat, StatLabel, StatNumber, Icon, Flex, SkeletonText). Potentially react-icons or other icon library.  
  3. Define props: interface StatsCardProps { label: string; value: number | string | undefined; icon?: React.ElementType; isLoading?: boolean; }.  
  4. Render a styled Box containing the Chakra Stat component.  
  5. Use StatLabel for props.label.  
  6. Use StatNumber for props.value.  
  7. Conditionally render props.icon using Icon.  
  8. **Loading State:** If props.isLoading is true, render \<SkeletonText noOfLines={1} /\> for the label and number instead of the actual StatLabel and StatNumber.  
  9. Style according to **KC-ANALYTICS-UX-1** design.  
  10. Write unit tests (**KC-ANALYTICS-TEST-FE-1**) testing rendering with different props and verifying the loading state shows skeletons.

**5\. Ticket: KC-ANALYTICS-FE-1: Implement Dashboard Page Layout**

* **Prompt:** Implement the basic layout structure for the dashboard page, as specified in **JIRA Ticket KC-ANALYTICS-FE-1**.  
  1. Modify/use the dashboard page route (e.g., src/app/(protected)/dashboard/page.tsx). Ensure it uses AuthGuard (**KC-AUTH-FE-4**).  
  2. Import Chakra UI components (Box, Heading, SimpleGrid, SkeletonText).  
  3. Add a Heading for the page title (e.g., "Dashboard").  
  4. Use SimpleGrid with appropriate columns or minChildWidth based on the design (**KC-ANALYTICS-UX-1**) to arrange the stats area.  
  5. Inside the SimpleGrid, render placeholder skeletons (e.g., 3 SkeletonText components with appropriate height/lines) where the StatsCard components will eventually go. This represents the initial loading state before data is fetched in **KC-ANALYTICS-FE-3**.  
  6. Write basic unit tests (**KC-ANALYTICS-TEST-FE-1**) verifying the page structure (title, grid, initial skeletons).

**6\. Ticket: KC-ANALYTICS-FE-3: Integrate API Data into Dashboard UI**

* **Prompt:** Fetch statistics from the API and display them on the dashboard using the StatsCard component, as specified in **JIRA Ticket KC-ANALYTICS-FE-3**.  
  1. Modify the dashboard page component (src/app/(protected)/dashboard/page.tsx). Mark as 'use client'.  
  2. Import useEffect, useState, StatsCard (**KC-ANALYTICS-FE-2**). Consider importing useSWR or similar data fetching hook.  
  3. **Data Fetching:**  
     * Define state: stats: { cardCount: number, tagCount: number, folderCount: number } | null, isLoading: boolean, error: string | null.  
     * Use useEffect \+ fetch (or useSWR) to call GET /api/analytics/stats.  
     * Set isLoading appropriately during the fetch lifecycle.  
     * On success, update stats state. On failure, set error state.  
  4. **Rendering:**  
     * In the SimpleGrid (from **KC-ANALYTICS-FE-1**):  
       * Replace the placeholder skeletons.  
       * Render three StatsCard components.  
       * Pass the fetched data and loading state to the props:  
         * \<StatsCard label="Total Cards" value={stats?.cardCount} isLoading={isLoading} /\>  
         * \<StatsCard label="Total Tags" value={stats?.tagCount} isLoading={isLoading} /\>  
         * \<StatsCard label="Total Folders" value={stats?.folderCount} isLoading={isLoading} /\>  
       * Add optional icons if desired.  
     * Display an error message if the error state is set.  
  5. Write unit tests (**KC-ANALYTICS-TEST-FE-1**) mocking the API call (fetch or SWR hook) and verifying that StatsCard components are rendered correctly with data in success state, show loading state, and display an error message on fetch failure.

**7\. Ticket: KC-ANALYTICS-TEST-BE-1: Write Unit Tests for Stats API Logic**

* **Prompt:** Write unit tests for the GET /api/analytics/stats endpoint using Jest/Vitest, as specified in **JIRA Ticket KC-ANALYTICS-TEST-BE-1**.  
  1. Create test file src/app/api/analytics/stats/route.test.ts.  
  2. Mock prisma.$transaction (or individual prisma.\*.count calls), getCurrentUserId.  
  3. Test success scenario: Mock getCurrentUserId returns a userId. Mock $transaction resolves with an array of counts (e.g., \[10, 5, 3\]). Assert 200 status and correct JSON response { cardCount: 10, tagCount: 5, folderCount: 3 }. Verify the where clauses passed to mocked count calls include the correct userId and relation checks (especially for tags).  
  4. Test zero counts scenario: Mock $transaction resolves with \[0, 0, 0\]. Assert 200 status and zero counts.  
  5. Test auth failure: Mock getCurrentUserId returns null. Assert 401 status.  
  6. Test DB error: Mock $transaction rejects. Assert 500 status.

**8\. Ticket: KC-ANALYTICS-TEST-FE-1: Write Unit Tests for Dashboard UI Components**

* **Prompt:** Write unit tests for the Dashboard frontend components using Jest and React Testing Library, as specified in **JIRA Ticket KC-ANALYTICS-TEST-FE-1**.  
  1. Create test files src/components/analytics/StatsCard.test.tsx and src/app/(protected)/dashboard/page.test.tsx.  
  2. Mock fetch or data fetching hooks (e.g., useSWR). Use renderWithProviders.  
  3. **StatsCard Tests:** Render with different props (label, value, icon?). Assert rendered output. Test isLoading prop renders SkeletonText.  
  4. **Dashboard Page Tests:**  
     * Mock the data fetching hook/fetch to simulate different states (loading, success with data, error).  
     * Test loading state: Assert StatsCard components receive isLoading={true} (which should render skeletons).  
     * Test success state: Assert StatsCard components receive isLoading={false} and the correct value props based on mocked data.  
     * Test error state: Assert an error message is displayed.