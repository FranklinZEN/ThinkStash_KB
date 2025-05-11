# **Review and AI Prompts for KC-SEARCH Epic (Stage 1 \- PG FTS)**

This document contains the technical review and AI development prompts for the KC-SEARCH epic (Stage 1), focusing on implementing basic keyword search using PostgreSQL Full-Text Search.

## **Part 1: Tech Lead Review of KC-SEARCH Epic (Stage 1 \- PG FTS)**

This epic implements the essential feature of searching through knowledge cards based on keywords. It specifically leverages PostgreSQL's built-in Full-Text Search (FTS) capabilities for performance, targeting card titles and the text content within the BlockNote JSON structure.

**A. Alignment and Coverage:**

* **PRD/TDD/ADRs:** Aligns with PRD requirement FR-SEARCH-1 and utilizes the existing technical stack (Next.js, Prisma, PostgreSQL, Chakra UI, NextAuth.js). The choice of PostgreSQL FTS is a key technical decision for this epic.  
* **Completeness:** Covers the core search workflow: UX design for input and results, backend API endpoint implementing the FTS query, frontend components for search input (with debouncing) and results display, and testing strategies for both backend and frontend.

**B. Key Technical Points & Considerations:**

* **PostgreSQL Full-Text Search (FTS):**  
  * **Core Technology:** This epic relies heavily on database-level features. Implementation requires understanding FTS concepts like tsvector, tsquery, matching operators (@@), and helper functions (to\_tsvector, websearch\_to\_tsquery, ts\_headline).  
  * **Indexing (KC-51/52):** Efficient FTS requires dedicated GIN indexes. Crucially, creating these indexes (and potentially helper functions like extract\_card\_text) often requires **raw SQL within Prisma migrations**, as prisma migrate dev doesn't automatically generate them from schema definitions or raw query usage. This adds a layer of complexity to migration management. The ticket provides examples for indexing title or title \+ extracted content. The combined index offers broader search but requires a robust extract\_card\_text function tailored to the BlockNote JSON structure.  
  * **JSONB Content Extraction (KC-51/52):** Searching within the content JSONB field requires extracting relevant text. The ticket proposes a PostgreSQL function (extract\_card\_text) for this. This function needs careful implementation and testing to correctly pull text from various BlockNote block types (paragraphs, headings, lists, etc.) while remaining IMMUTABLE for indexing purposes.  
  * **Prisma Raw Queries (KC-51/52):** The search API endpoint will use Prisma's $queryRawUnsafe (or potentially $queryRaw if types align perfectly, which is less likely with FTS functions) to execute the FTS query. Parameter binding is essential to prevent SQL injection vulnerabilities.  
  * **Highlighting (KC-51/52):** Uses ts\_headline to generate snippets with highlighted keywords, enhancing the user experience. Frontend needs to handle the output, which might include HTML tags.  
* **Frontend Implementation:**  
  * **Debouncing (KC-SEARCH-FE-1):** The search input component correctly includes debouncing logic to prevent excessive API calls while the user is typing.  
  * **Results Display (KC-SEARCH-FE-2):** Needs to handle the API response, including the optional headline field. Rendering the headline might require using dangerouslySetInnerHTML if it contains HTML tags, which necessitates careful consideration of potential XSS risks (though output from ts\_headline with standard options is generally safe, sanitization is best practice if unsure).  
* **Testing:**  
  * **Backend (KC-SEARCH-TEST-BE-1):** Unit testing raw SQL queries is difficult. The prompt rightly emphasizes mocking $queryRawUnsafe to verify query structure and parameter passing. However, **integration testing** against a real PostgreSQL instance (potentially using tools like testcontainers) is highly recommended to truly validate the FTS indexing and query logic.  
  * **Frontend (KC-SEARCH-TEST-FE-1):** Focuses on testing component logic, debouncing, state handling, and rendering, including the headline snippet.

**C. Potential Gaps/Refinements:**

* **Migration Management:** The process for adding raw SQL (indexes, functions) to Prisma migrations needs to be clearly defined and followed.  
* **FTS Configuration/Tuning:** Uses 'english' configuration by default. More advanced scenarios might require different languages or custom dictionaries. Query formatting (websearch\_to\_tsquery vs. plainto\_tsquery) and ranking options offer room for future tuning.  
* **Error Handling:** Specific FTS query syntax errors from PostgreSQL might need more granular handling than a generic 500 error.  
* **JSONB Extraction Robustness:** The example extract\_card\_text function is basic. It needs to be thoroughly tested and potentially expanded to handle all relevant BlockNote block types used in the application.

**D. Implicit Decisions:**

* Search implementation relies on database FTS rather than application-level filtering or external search engines (like ElasticSearch) for Stage 1\.  
* Basic keyword matching with optional highlighting is the target functionality. Advanced features like filtering by tags/folders within search results are not included in this stage.

This epic introduces powerful search capabilities but requires careful database-level setup and specific Prisma query techniques. Managing migrations with raw SQL and ensuring the JSONB text extraction is accurate are key challenges. Integration testing for the backend API is strongly advised.

## **Part 2: AI Development Prompts for KC-SEARCH Epic (Stage 1 \- PG FTS)**

*(Prompts reference the full suite of project documents and incorporate review findings)*

**1\. Ticket: KC-SEARCH-UX-1: Design Search UI & Results Display**

* **Prompt (For TL/Dev Reference):** Review and finalize the UX designs for the search interface as specified in **JIRA Ticket KC-SEARCH-UX-1**. Ensure designs:  
  * Detail the search input field's appearance and placement (e.g., header).  
  * Define the layout for displaying search results (page or section).  
  * Specify the content and layout of individual result items (title, highlighted snippet via ts\_headline, tags, etc.).  
  * Include states for loading, empty results ("No results found").  
  * Address responsiveness and accessibility (labels, keyboard navigation).  
  * These designs guide **KC-SEARCH-FE-1** and **KC-SEARCH-FE-2**.

**2\. Ticket: KC-51 & KC-52 (Combined): Create API endpoint for Basic Keyword Search (PostgreSQL FTS)**

* **Prompt:** Implement the GET /api/search endpoint using PostgreSQL FTS, as specified in **JIRA Tickets KC-51 & KC-52**.  
  1. **Migration (Raw SQL):** Create a new Prisma migration file (prisma/migrations/.../migration.sql). Add raw SQL to:  
     * Create the extract\_card\_text(jsonb) PostgreSQL function. **Refine the provided example function** to accurately extract text from all relevant BlockNote block types used (paragraphs, headings, lists, etc.). Ensure it's IMMUTABLE.  
     * Create a GIN FTS index on Card using to\_tsvector('english', ...) on title and the result of extract\_card\_text(content). Example: CREATE INDEX card\_full\_text\_idx ON "Card" USING gin(to\_tsvector('english', title || ' ' || extract\_card\_text(content)));.  
     * Apply the migration: npx prisma migrate dev.  
  2. **API Route (app/api/search/route.ts):**  
     * Export async GET(request: Request). Import NextResponse, prisma, getCurrentUserId.  
     * Auth check: const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }.  
     * Get query param: const query \= new URL(request.url).searchParams.get('q');. Return 400 if missing or empty.  
     * Prepare FTS query string (e.g., using websearch\_to\_tsquery). Sanitize/format user input appropriately. const searchQuery \= query.trim().split(/\\s+/).join(' & '); // Example  
     * Use prisma.$queryRawUnsafe\<CardSearchResult\[\]\>(...) to execute the FTS query.  
       SELECT  
         c.id, c.title, c."updatedAt",  
         ts\_headline('english', c.title || ' ' || extract\_card\_text(c.content), websearch\_to\_tsquery('english', $1), 'StartSel=\*\*,StopSel=\*\*,MaxWords=35,MinWords=15,HighlightAll=TRUE') as headline,  
         \-- Fetch tags (consider efficiency \- subquery or separate query might be needed)  
         (SELECT json\_agg(json\_build\_object('name', t.name)) FROM "\_CardToTag" ct JOIN "Tag" t ON ct."B" \= t.id WHERE ct."A" \= c.id LIMIT 5\) as tags  
       FROM  
         "Card" c  
       WHERE  
         c."userId" \= $2 AND  
         \-- The FTS condition using the index:  
         to\_tsvector('english', c.title || ' ' || extract\_card\_text(c.content)) @@ websearch\_to\_tsquery('english', $1)  
       ORDER BY  
         c."updatedAt" DESC \-- Add relevance ranking later if needed (ts\_rank\_cd)  
       LIMIT 50;

     * Pass searchQuery and userId as parameters ($1, $2).  
     * Define CardSearchResult type including headline: string | null and tags: {name: string}\[\] | null.  
     * Post-process results (e.g., ensure tags is an array r.tags || \[\]).  
     * Return NextResponse.json(processedResults);.  
     * Include try/catch, handling potential FTS syntax errors and generic 500s.  
  3. Write tests (**KC-SEARCH-TEST-BE-1**), focusing on mocking $queryRawUnsafe to verify query structure and parameters. **Strongly recommend integration tests** against a real PostgreSQL DB with the index/function created.

**3\. Ticket: KC-SEARCH-FE-1: Implement Search Input Component**

* **Prompt:** Create the reusable SearchInput component with debouncing, as specified in **JIRA Ticket KC-SEARCH-FE-1**.  
  1. Create src/components/search/SearchInput.tsx. Mark as 'use client'.  
  2. Import useState, useEffect, useRef, Chakra components (InputGroup, Input, InputRightElement, IconButton), icons (SearchIcon, CloseIcon).  
  3. Props: interface SearchInputProps { onSearch: (query: string) \=\> void; initialQuery?: string; isLoading?: boolean; }.  
  4. State: query: string (controlled input value). Ref: debounceTimeoutRef \= useRef\<NodeJS.Timeout | null\>(null);.  
  5. handleInputChange: Update query state. Clear existing timeout (clearTimeout(debounceTimeoutRef.current)). Set new setTimeout (\~300-500ms) that calls props.onSearch(newQueryValue). Store timeout ID in debounceTimeoutRef.current.  
  6. useEffect cleanup: return () \=\> { if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current); };.  
  7. handleClear: Set query(''), call props.onSearch(''), clear timeout.  
  8. Render InputGroup with Input bound to query state and onChange. Add conditional InputRightElement with CloseIcon IconButton (onClick={handleClear}) when query is not empty and \!isLoading. Show Spinner if isLoading.  
  9. Style according to **KC-SEARCH-UX-1**.  
  10. Write unit tests (**KC-SEARCH-TEST-FE-1**) covering input changes, debouncing logic (use fake timers), clear button, isLoading state.

**4\. Ticket: KC-SEARCH-FE-2: Implement Search Results Display Page/Section**

* **Prompt:** Implement the UI for displaying search results, as specified in **JIRA Ticket KC-SEARCH-FE-2**.  
  1. Create page src/app/(protected)/search/page.tsx (or integrate into existing page). Mark as 'use client'. Wrap route/layout with AuthGuard.  
  2. Import useState, useEffect, SearchInput (**KC-SEARCH-FE-1**), Chakra components (Box, VStack, Heading, Text, Spinner, Link), define CardSearchResult type (matching API response).  
  3. State: results: CardSearchResult\[\], isLoading: boolean, error: string | null, searchQuery: string.  
  4. Implement handleSearch \= async (query: string) \=\> { ... }:  
     * Set searchQuery(query). If query is empty, clear results and return.  
     * Set isLoading(true), setError(null).  
     * fetch(\\/api/search?q=${encodeURIComponent(query)}\`)\`.  
     * Handle success: setResults(await response.json()).  
     * Handle failure: setError('Search failed.').  
     * Set isLoading(false) in finally block.  
  5. Render SearchInput component, passing handleSearch and isLoading.  
  6. Render results area:  
     * Show Spinner if isLoading.  
     * Show error message if error.  
     * If \!isLoading && \!error && results.length \=== 0 && searchQuery, show "No results found".  
     * If results.length \> 0, map results to SearchResultItem components.  
  7. Create SearchResultItem component (src/components/search/SearchResultItem.tsx):  
     * Props: result: CardSearchResult.  
     * Render Link (from next/link) to /cards/${result.id}.  
     * Display result.title.  
     * Display result.tags.  
     * Display result.headline. **If using dangerouslySetInnerHTML={{ \_\_html: result.headline }} for highlighting, ensure the source (ts\_headline output) is trusted or consider sanitizing the HTML.** Alternatively, manually parse \*\* tags if that's the format used.  
  8. Style according to **KC-SEARCH-UX-1**.  
  9. Write tests (**KC-SEARCH-TEST-FE-1**) covering handleSearch logic, rendering different states (loading, error, no results, results list), and SearchResultItem rendering (especially headline).

**5\. Ticket: KC-SEARCH-TEST-BE-1: Write Unit/Integration Tests for Search API Logic (PostgreSQL FTS)**

* **Prompt:** Write tests for the GET /api/search endpoint using Jest/Vitest, as specified in **JIRA Ticket KC-SEARCH-TEST-BE-1**.  
  1. Create test file tests/integration/api/search/route.test.ts.  
  2. Mock prisma.$queryRawUnsafe, getCurrentUserId.  
  3. Test successful search: Mock getCurrentUserId (returns userId). Mock prisma.$queryRawUnsafe to return mock results array (including headline). Verify $queryRawUnsafe is called with expected SQL structure (FTS functions, WHERE, parameters). Assert 200 status and response body.  
  4. Test empty query: Verify API returns empty array without calling DB.  
  5. Test no results: Mock $queryRawUnsafe returns empty array. Assert 200 status and empty array response.  
  6. Test auth error: Mock getCurrentUserId returns null. Assert 401\.  
  7. Test DB error: Mock $queryRawUnsafe throws error. Assert 500\.  
  8. **Recommendation:** Supplement with integration tests against a real PostgreSQL test database (using e.g., testcontainers) to validate FTS index/function behavior directly.

**6\. Ticket: KC-SEARCH-TEST-FE-1: Write Unit Tests for Search UI Components**

* **Prompt:** Write unit tests for the Search frontend components using Jest and React Testing Library, as specified in **JIRA Ticket KC-SEARCH-TEST-FE-1**.  
  1. Create test files src/components/search/SearchInput.test.tsx and src/app/(protected)/search/page.test.tsx (or similar).  
  2. Mock fetch, next/navigation. Use renderWithProviders.  
  3. **SearchInput Tests:** Use fake timers (jest.useFakeTimers). Test input updates state. Test onSearch is called only *after* debounce delay (jest.advanceTimersByTime). Test clear button resets state and calls onSearch(''). Test isLoading prop shows spinner.  
  4. **Search Results Page Tests:**  
     * Mock fetch.  
     * Test initial render state.  
     * Simulate search via SearchInput interaction (fireEvent.change, advance timers). Assert fetch is called with correct URL.  
     * Test loading state rendering while fetch is pending.  
     * Test rendering results: Mock fetch success. Assert results (including headlines) are rendered correctly. Test dangerouslySetInnerHTML usage if applicable.  
     * Test "No results found" state.  
     * Test error state rendering.