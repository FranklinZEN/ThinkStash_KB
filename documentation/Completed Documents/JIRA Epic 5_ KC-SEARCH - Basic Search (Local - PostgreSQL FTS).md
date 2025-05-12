## **JIRA Epic: KC-SEARCH \- Basic Search (Stage 1 \- PostgreSQL FTS Version)**

**Rationale:** Provide essential keyword search capability over locally stored card data (title and basic text content) using efficient PostgreSQL Full-Text Search.

Ticket ID: KC-SEARCH-UX-1  
Title: Design Search UI & Results Display  
Epic: KC-SEARCH  
PRD Requirement(s): FR-SEARCH-1  
Team: UX  
Dependencies (Functional): KC-SETUP-3 (Chakra UI)  
UX/UI Design Link: \[Link to Figma/mockups\]  
Description (Functional): Design the user interface for initiating a search (e.g., a search bar in the header or main area) and displaying the list of matching knowledge cards.  
Acceptance Criteria (Functional):

* Mockups show the placement and appearance of the search input field.  
* Designs detail the layout of the search results page or area.  
* Mockups show how individual search results (matching cards) are presented (e.g., Card Title, snippet of matching text using ts\_headline, tags, last updated).  
* Designs specify behavior for empty search results ("No results found").  
* Designs specify handling of loading state while search is in progress.  
* Designs are responsive and include detailed specs.  
  Technical Approach / Implementation Notes:  
* Specify search input states (placeholder, active, clear button).  
* Define the structure of a single search result item (consider reusing card list item components).  
* Detail how matching keywords could be highlighted in the title or snippet (using PostgreSQL's ts\_headline function in the backend query).  
* Ensure accessibility (label for search input, keyboard navigation for results).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved: N/A (Design artifact)  
  Testing Considerations (Technical): Usability testing on prototypes. Accessibility review.  
  Dependencies (Technical): KC-SETUP-3

Ticket ID: KC-51 & KC-52 (Combined)  
Title: Create API endpoint for Basic Keyword Search (PostgreSQL FTS)  
Epic: KC-SEARCH  
PRD Requirement(s): FR-SEARCH-1  
Team: BE  
Dependencies (Functional): KC-20.1-BLOCK (Card Schema with JSONB), KC-8.2 (Auth Check), KC-SETUP (PostgreSQL env)  
UX/UI Design Link: N/A  
Description (Functional): Implement the backend logic to search through the user's cards based on a keyword query, using PostgreSQL's Full-Text Search capabilities for efficient matching against card titles and text content within the JSONB field.  
Acceptance Criteria (Functional):

* Sending a GET request to /api/search?q={query} returns a list of cards owned by the logged-in user where the query matches the indexed text content (title \+ relevant JSON blocks) according to PostgreSQL FTS rules.  
* Search results can optionally include a highlighted snippet (headline) showing the match context.  
* Returns an empty list if no matches are found or the query is empty/invalid FTS query.  
* Returns 401 Unauthorized if the user is not logged in.  
* Returns 400 Bad Request if the query parameter q is missing.  
  Technical Approach / Implementation Notes:  
* Create app/api/search/route.ts. Export async function GET(request: Request).  
* Import NextResponse, prisma, getCurrentUserId. Use URL object.  
* const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
* Get and validate query param q.  
* **PostgreSQL FTS Approach:**  
  * **Indexing Strategy (Requires Migration):** For efficient search, create FTS indexes in PostgreSQL. This typically involves a separate Prisma migration (db push won't create indexes automatically from raw queries).  
    * **Option 1 (Simpler Index):** Index the title field directly.  
      \-- In a migration file (e.g., using ALTER TABLE or CREATE INDEX)  
      CREATE INDEX card\_title\_fts\_idx ON "Card" USING gin(to\_tsvector('english', title));

    * **Option 2 (Combined Index \- More Complex):** Create an index on both title and extracted text from the content JSONB. This might require a generated column in Postgres or indexing an immutable function result.  
      \-- Example: Create function to extract text (needs refinement based on BlockNote structure)  
      CREATE OR REPLACE FUNCTION extract\_card\_text(content jsonb) RETURNS text AS $$  
      DECLARE  
          block jsonb;  
          text\_content text := '';  
          inline\_content jsonb;  
          inline\_item jsonb;  
      BEGIN  
          IF content IS NULL THEN RETURN ''; END IF;  
          FOR block IN SELECT jsonb\_array\_elements(content) LOOP  
              IF block-\>\>'type' LIKE 'paragraph' OR block-\>\>'type' LIKE 'heading%' THEN  
                  IF block-\>'content' IS NOT NULL THEN  
                       FOR inline\_item IN SELECT jsonb\_array\_elements(block-\>'content') LOOP  
                           IF inline\_item-\>\>'type' \= 'text' THEN  
                               text\_content := text\_content || ' ' || (inline\_item-\>\>'text');  
                           END IF;  
                       END LOOP;  
                  END IF;  
              END IF;  
              \-- Add logic for other block types (lists, etc.) if needed  
          END LOOP;  
          RETURN text\_content;  
      END;  
      $$ LANGUAGE plpgsql IMMUTABLE;

      \-- Example: Create index on title \+ extracted content  
      CREATE INDEX card\_full\_text\_idx ON "Card" USING gin(to\_tsvector('english', title || ' ' || extract\_card\_text(content)));

  * **API Query Logic:** Use Prisma's $queryRaw or $queryRawUnsafe to execute the FTS query.  
    import { Prisma } from '@prisma/client'; // For raw query types if needed

    // ... inside GET handler ...  
    if (\!query || query.trim() \=== '') { return NextResponse.json(\[\]); }

    // Sanitize and format the query for FTS (e.g., websearch\_to\_tsquery or plainto\_tsquery)  
    // 'websearch\_to\_tsquery' is often good for user input  
    const searchQuery \= query.trim().split(/\\s+/).join(' & '); // Simple 'AND' logic, adjust as needed

    try {  
      // Use queryRawUnsafe as ts\_query functions might not be typed by Prisma  
      // Select desired fields \+ headline/rank for relevance  
      const results \= await prisma.$queryRawUnsafe\<CardSearchResult\[\]\>(  
        \`SELECT  
           c.id, c.title, c."updatedAt",  
           ts\_headline('english', c.title || ' ' || extract\_card\_text(c.content), websearch\_to\_tsquery('english', $1), 'StartSel=\*\*,StopSel=\*\*,MaxWords=35,MinWords=15,HighlightAll=TRUE') as headline,  
           \-- Optional: Rank results based on relevance  
           \-- ts\_rank\_cd(to\_tsvector('english', c.title || ' ' || extract\_card\_text(c.content)), websearch\_to\_tsquery('english', $1)) as rank  
           (SELECT json\_agg(json\_build\_object('name', t.name)) FROM "\_CardToTag" ct JOIN "Tag" t ON ct."B" \= t.id WHERE ct."A" \= c.id) as tags \-- Fetch tags separately or join differently  
         FROM  
           "Card" c  
         WHERE  
           c."userId" \= $2 AND  
           to\_tsvector('english', c.title || ' ' || extract\_card\_text(c.content)) @@ websearch\_to\_tsquery('english', $1)  
         ORDER BY \-- Optional ranking  
           \-- rank DESC,  
           c."updatedAt" DESC  
         LIMIT 50;\`, // Add LIMIT for safety  
        searchQuery, // $1 parameter  
        userId       // $2 parameter  
      );  
      // Note: Fetching tags like this might be inefficient; adjust as needed.

      // Post-process results if necessary (e.g., parse tags JSON)  
      const processedResults \= results.map(r \=\> ({ ...r, tags: r.tags || \[\] }));

      return NextResponse.json(processedResults);

    } catch (error) {  
      console.error("Search API error:", error);  
      // Handle specific FTS query syntax errors if possible  
      return NextResponse.json({ error: 'Search failed' }, { status: 500 });  
    }

    *(Define CardSearchResult type including headline and parsed tags)*.  
* Remove the old backend filtering logic and extractTextFromBlockContent helper (or keep helper if used in index function).  
  API Contract (if applicable):  
* **Endpoint:** GET /api/search  
* **Request:** Query parameter q=string. Auth via session.  
* **Response Success (200):** Array\<{ id: string, title: string, updatedAt: Date, tags: Array\<{ name: string }\>, headline?: string }\> (Includes optional highlighted snippet).  
* **Response Error (401):** { error: 'Unauthorized' }  
* **Response Error (400):** { error: 'Missing search query' }  
* Response Error (500): { error: 'Search failed' } (Or more specific FTS error)  
  Data Model Changes (if applicable): Requires adding FTS indexes via migrations (not directly changing schema.prisma). May require helper functions or generated columns in Postgres.  
  Key Functions/Modules Involved:  
* app/api/search/route.ts  
* lib/sessionUtils.ts, lib/prisma.ts ($queryRawUnsafe)  
* PostgreSQL FTS functions (to\_tsvector, websearch\_to\_tsquery, @@, ts\_headline).  
* Prisma migration files (for creating indexes/functions).  
  Testing Considerations (Technical): Test searching by title, by content. Test FTS query syntax variations. Test highlighting (ts\_headline). Test relevance ranking (if implemented). Test auth (401). Unit testing raw SQL queries is harder; focus on integration tests or carefully testing the query logic manually and ensuring parameters are passed correctly.  
  Dependencies (Technical): KC-20.1-BLOCK, KC-8.2, PostgreSQL database with FTS extensions enabled.

Ticket ID: KC-SEARCH-FE-1  
Title: Implement Search Input Component  
Epic: KC-SEARCH  
PRD Requirement(s): FR-SEARCH-1  
Team: FE  
Dependencies (Functional): KC-SEARCH-UX-1 (Design), KC-SETUP-3 (Chakra UI)  
UX/UI Design Link: \[Link to Figma/mockups for Search Input\]  
Description (Functional): Create a reusable search input component, potentially including features like debouncing and clearing the input.  
Acceptance Criteria (Functional):

* A search input field is rendered according to the design.  
* Typing into the input updates the component's state.  
* A callback prop (onSearch) is triggered with the search query after a short delay (debouncing) to avoid excessive API calls.  
* An optional clear button allows resetting the input field.  
* Matches the visual design from KC-SEARCH-UX-1.  
  Technical Approach / Implementation Notes:  
* Create src/components/search/SearchInput.tsx. Mark as 'use client'.  
* Import useState, useEffect, useRef, Chakra components (InputGroup, Input, InputRightElement, IconButton, Spinner), icons (SearchIcon, CloseIcon).  
* Use useState for the query: string. Use useRef for debounce timeout ID.  
* **Debouncing:**  
  * In handleInputChange: Update query state. Clear existing timeout. Set new setTimeout to call props.onSearch(newQueryValue) after delay (e.g., 300-500ms). Store timeout ID in ref.  
  * Ensure useEffect cleanup clears the timeout.  
* Implement handleClear function to reset query and call props.onSearch(''). Clear any pending debounce timeout.  
* Render InputGroup containing Input (bind value to query, onChange to handleInputChange) and potentially InputRightElement with IconButton (clear button, conditional display) or Spinner (controlled by isLoading prop).  
* Define props: interface SearchInputProps { onSearch: (query: string) \=\> void; initialQuery?: string; isLoading?: boolean; }.  
  API Contract (if applicable): N/A (UI Component)  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/components/search/SearchInput.tsx  
* React useState, useEffect, useRef  
* Debouncing logic (setTimeout)  
* Chakra UI components  
  Testing Considerations (Technical): Unit test input changes, debouncing logic (verify onSearch called after delay and not on every keystroke, using fake timers), clear button functionality.  
  Dependencies (Technical): KC-SEARCH-UX-1, KC-SETUP-3

Ticket ID: KC-SEARCH-FE-2  
Title: Implement Search Results Display Page/Section  
Epic: KC-SEARCH  
PRD Requirement(s): FR-SEARCH-1  
Team: FE  
Dependencies (Functional): KC-51/52 (Search API \- PG Version), KC-SEARCH-FE-1 (Input Comp), KC-CARD-FE-6-BLOCK (Card List Item Reuse?), KC-SEARCH-UX-1 (Design)  
UX/UI Design Link: \[Link to Figma/mockups for Search Results\]  
Description (Functional): Create the UI area or page where search results are displayed, handling loading states, empty results, and potentially highlighting matched text snippets.  
Acceptance Criteria (Functional):

* A dedicated page (e.g., /search) or section displays search results.  
* Integrates the SearchInput component.  
* When a search is performed (via SearchInput's onSearch callback), it calls the GET /api/search endpoint.  
* Displays a loading indicator while the API call is in progress.  
* Renders the list of matching cards returned by the API, using a suitable card item representation (title, highlighted headline snippet, tags).  
* Displays a "No results found" message if the API returns an empty list.  
* Handles API errors gracefully.  
  Technical Approach / Implementation Notes:  
* Create page src/app/(protected)/search/page.tsx (or integrate). Mark as 'use client'.  
* Import useState, SearchInput, Chakra components, Link, potentially a SearchResultItem component.  
* Use useState for results: CardSearchResult\[\], isLoading: boolean, error: string | null, currentQuery: string. (Define CardSearchResult type including headline).  
* Implement handleSearch(query: string) function:  
  * If query is empty, clear results, return.  
  * setCurrentQuery(query); setIsLoading(true); setError(null);  
  * Call fetch(\\/api/search?q=${encodeURIComponent(query)}\`)\`.  
  * Handle success/failure, update state (results, error).  
  * setIsLoading(false);  
* Render SearchInput, passing handleSearch and isLoading.  
* Render results section:  
  * Handle loading, error, no results states.  
  * If results exist, map over results and render each item using SearchResultItem.  
  * SearchResultItem component:  
    * Takes result: CardSearchResult prop.  
    * Displays result.title.  
    * Displays result.tags.  
    * Displays the result.headline snippet, potentially using dangerouslySetInnerHTML if the headline contains HTML tags (like \*\*) from ts\_headline. **Sanitize carefully if using dangerouslySetInnerHTML**, or parse the tags manually.  
    * Links to /cards/${result.id}.  
      API Contract (if applicable): Consumes GET /api/search?q={query} (KC-51/52 \- PG Version).  
      Data Model Changes (if applicable): N/A  
      Key Functions/Modules Involved:  
* src/app/(protected)/search/page.tsx (or similar)  
* src/components/search/SearchInput.tsx  
* src/components/search/SearchResultItem.tsx  
* React useState, fetch  
* Chakra UI components  
* HTML parsing/sanitization for headline (if needed).  
  Testing Considerations (Technical): E2E test searching and viewing results with headlines. Unit test handleSearch logic, rendering logic for different states, and SearchResultItem rendering (including headline handling).  
  Dependencies (Technical): KC-51/52 (PG Version), KC-SEARCH-FE-1, KC-SEARCH-UX-1

Ticket ID: KC-SEARCH-TEST-BE-1 (Generated)  
Title: Write Unit/Integration Tests for Search API Logic (PostgreSQL FTS)  
Epic: KC-SEARCH  
PRD Requirement(s): NFR-MAINT-1  
Team: BE/QA  
Dependencies (Functional): KC-51/52 (Search API \- PG Version), KC-72 (Auth Test Setup)  
UX/UI Design Link: N/A  
Description (Functional): Create automated tests for the backend search API endpoint using PostgreSQL FTS.  
Acceptance Criteria (Functional):

* Tests verify successful search matching title and content using mocked raw FTS queries.  
* Tests verify handling of FTS query syntax (e.g., websearch\_to\_tsquery).  
* Tests verify highlighting (ts\_headline) and ranking (if implemented) logic in the raw query.  
* Tests verify handling of empty query and no-result scenarios.  
* Tests verify authentication requirement (401).  
* Tests cover database error handling (500).  
  Technical Approach / Implementation Notes:  
* Use Jest/Vitest. Create test file `tests/integration/api/search/route.test.ts`.
* **Mock Dependencies:** Mock `prisma.$queryRawUnsafe`, `getCurrentUserId`.
* **Test Cases:**
  * Success: Mock `getCurrentUserId` (return userId), mock `$queryRawUnsafe` (return mock results including `headline`). Assert 200 status and response body. Verify query structure and parameters passed to `$queryRawUnsafe`.
  * Empty Query: Assert 200 status and empty array response without DB call.
  * No Results: Mock `$queryRawUnsafe` returns empty array. Assert 200 status and empty array response.
  * Auth Error (401): Mock `getCurrentUserId` returns null.
  * DB Error (500): Mock `$queryRawUnsafe` throws error.
* **Note:** Strongly recommend supplementing with integration tests against a real PostgreSQL test database to validate FTS index/function behavior directly.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved:
* `app/api/search/route.ts`
* Jest/Vitest, mocks.
Testing Considerations (Technical): Ensure mocks verify SQL structure and parameters. Integration testing is crucial for FTS validation.
Dependencies (Technical): KC-51/52 (PG Version), Testing framework setup.

Ticket ID: KC-SEARCH-TEST-FE-1 (Generated)  
Title: Write Unit Tests for Search UI Components  
Epic: KC-SEARCH  
PRD Requirement(s): NFR-MAINT-1  
Team: FE/QA  
Dependencies (Functional): KC-SEARCH-FE-1 (Input Comp), KC-SEARCH-FE-2 (Results Display), KC-TEST-FE-1
UX/UI Design Link: N/A
Description (Functional): Create automated unit tests for the frontend SearchInput and Search Results components.
Acceptance Criteria (Functional):
* Tests verify SearchInput component's debouncing logic correctly calls `onSearch` after delay.
* Tests verify SearchInput's clear button functionality.
* Tests verify SearchInput's loading state display.
* Tests verify Search Results page/component correctly calls search API via `handleSearch`.
* Tests verify Search Results page/component correctly renders loading, error, no results, and results list states.
* Tests verify SearchResultItem component renders title, tags, and highlighted headline correctly (including handling potential HTML).
Technical Approach / Implementation Notes:
* Use Jest/Vitest and React Testing Library.
* **SearchInput Tests:** Use Jest fake timers (`jest.useFakeTimers`). Simulate input changes (`fireEvent.change`), advance timers (`jest.advanceTimersByTime`), assert `onSearch` mock calls. Test clear button (`fireEvent.click`) resets state and calls `onSearch`. Test `isLoading` prop shows spinner.
* **Search Results Page Tests:** Mock `fetch` (or SWR). Mock `useRouter`, `useToast` if used. Simulate search interaction trigger (`handleSearch`). Assert API call mock. Test rendering of different states (loading, error, no results, results list) based on API mock response. Assert `SearchResultItem` receives correct props.
* **SearchResultItem Tests:** Render component with mock data. Assert title, tags, headline are displayed. Test `dangerouslySetInnerHTML` usage/sanitization if applicable.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `src/components/search/SearchInput.tsx`, `src/app/(protected)/search/page.tsx` (or similar), `src/components/search/SearchResultItem.tsx`, Jest/Vitest, RTL, mocks.
Testing Considerations (Technical): Utilize fake timers for debouncing tests. Mock fetch/hooks effectively to test different UI states. Pay attention to testing headline rendering, especially if using `dangerouslySetInnerHTML`.
Dependencies (Technical): KC-SEARCH-FE-1, KC-SEARCH-FE-2, KC-TEST-FE-1