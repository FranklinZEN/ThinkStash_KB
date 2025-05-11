# **Review and AI Prompts for KC-CARD-CREATE Epic (Stage 1\)**

This document contains the technical review and AI development prompts for the KC-CARD-CREATE epic (Stage 1), focusing on implementing card CRUD operations using a block editor.

## **Part 1: Tech Lead Review of KC-CARD-CREATE Epic (Stage 1\)**

This epic implements the core functionality for users to create, read, update, and delete (CRUD) knowledge cards. Key features include using BlockNote.js for rich text editing, storing card content as JSON in the database, and adding support for tagging.

**A. Alignment and Coverage:**

* **PRD/TDD/ADRs:** The tickets generally align with the referenced PRD requirements (FR-CARD-1, FR-CARD-2) and build upon previous technical decisions (Next.js, PostgreSQL/Prisma, Chakra UI, NextAuth.js for auth checks, BlockNote.js chosen in KC-SETUP-3).  
* **Completeness:** The epic covers the full lifecycle for basic card management: UX design, schema definition (Card, Tag models), backend API endpoints (CRUD), frontend components (BlockEditor wrapper, TagInput, CRUD pages), and associated testing.

**B. Key Technical Points & Considerations:**

* **Block Editor Integration (BlockNote.js):**  
  * A dedicated component (KC-CARD-FE-1-BLOCK) wraps BlockNote, handling initialization, content changes, and read-only states.  
  * **Styling:** Requires careful customization (KC-CARD-FE-1-BLOCK) to align BlockNote's appearance with the Chakra UI theme and specific UX designs (KC-CARD-UX-1-BLOCK). This might involve theme overrides or custom CSS.  
  * **Content Storage:** Card content is stored as Json in Prisma (KC-20.1-BLOCK), mapping to jsonb in PostgreSQL. This is efficient but requires careful handling of serialization/deserialization. API endpoints must validate incoming JSON structure (KC-23-BLOCK, KC-CARD-BE-2-BLOCK).  
* **Tag Handling:**  
  * A many-to-many relationship between Cards and Tags is established (KC-20.1-BLOCK, KC-20.2).  
  * **Case-Insensitivity:** A critical requirement is handling tags case-insensitively (KC-25.1). The proposed solution involves normalization (lowercase) and checking for existing tags using Prisma's insensitive mode (if supported) or application-level filtering. This logic needs robust implementation and testing. The getTagConnectionsForUpsert helper is central to this.  
  * **UI:** A reusable TagInput component (KC-CARD-FE-7-BLOCK) provides the frontend interaction for adding/removing tags.  
* **API Design:** Standard RESTful principles are applied for card CRUD operations (/api/cards, /api/cards/{cardId}). Ownership checks (userId in where clauses) are correctly included in fetch/update/delete operations (KC-CARD-BE-1-BLOCK, KC-CARD-BE-2-BLOCK, KC-CARD-BE-3-BLOCK). Zod is used for request validation.  
* **Folder Association:** The Card schema (KC-20.1-BLOCK) includes an optional folderId, allowing basic association. However, more complex folder logic (creation, ownership checks during association) is deferred (mentioned as part of KC-ORG).  
* **Testing:** Comprehensive testing tickets (KC-CARD-TEST-BE-1-BLOCK, KC-CARD-TEST-FE-1-BLOCK) are included, covering both backend API logic (unit/integration) and frontend components/pages (unit/integration).

**C. Potential Gaps/Refinements:**

* **BlockNote JSON Validation:** While the API prompts mention basic z.array(z.any()) validation for BlockNote content, more specific validation against the PartialBlock structure might be beneficial if feasible without excessive complexity, potentially using a custom Zod schema or refinement.  
* **Error Handling Specificity:** API prompts mention generic 500 errors. Specific error handling (e.g., for Prisma unique constraint violations beyond email, or specific DB connection issues) could be detailed further in implementation or specific error handling guidelines.  
* **Folder Ownership (Deferred):** Explicitly note that while folderId can be set, validating that the folderId actually belongs to the user is not part of this epic and needs to be added later during folder implementation (KC-ORG).  
* **Tag Autocomplete (Deferred):** The TagInput prompt correctly notes autocomplete as a potential future enhancement.

**D. Implicit Decisions:**

* BlockNote.js is the chosen block editor library.  
* Card content is stored as JSON.  
* Tags are managed via a separate model with a many-to-many relationship.  
* Standard Next.js API routes and Prisma are used for the backend.

Overall, this epic provides a solid foundation for card creation and management using a modern block editor approach. Careful attention to BlockNote styling and robust implementation of case-insensitive tag handling are key areas for successful execution.

## **Part 2: AI Development Prompts for KC-CARD-CREATE Epic (Stage 1\)**

*(Prompts reference the full suite of project documents and incorporate review findings)*

**1\. Ticket: KC-CARD-UX-1-BLOCK: Design Block Editor Experience & Core Blocks**

* **Prompt (For TL/Dev Reference):** Review and finalize the UX designs for the block editor card creation/editing experience as specified in **JIRA Ticket KC-CARD-UX-1-BLOCK**. Ensure designs:  
  * Integrate BlockNote.js concepts (basic text blocks: Paragraph, H1-H3, Lists; slash commands; floating toolbar for Bold/Italic).  
  * Align visually with **ADR-006 (Chakra UI)** and the **UI Style Guide**.  
  * Clearly define the editor's appearance within the page context (Title, Tags, Save button).  
  * Specify BlockNote theme customizations or CSS overrides needed.  
  * Cover read-only appearance for card display.  
  * Include responsiveness and accessibility considerations.  
  * These designs are the primary reference for **KC-CARD-FE-1-BLOCK**, **KC-CARD-FE-7-BLOCK**, **KC-CARD-FE-2-BLOCK**, **KC-CARD-FE-3-BLOCK**, **KC-CARD-FE-4-BLOCK**.

**2\. Ticket: KC-20.1-BLOCK: Modify Card Schema for JSON Content**

* **Prompt:** Update the Prisma schema (prisma/schema.prisma) to define the Card model for storing block editor content as JSON, as specified in **JIRA Ticket KC-20.1-BLOCK**.  
  1. Define/Modify model Card with fields: id (String, cuid, id), title (String), content (Json), createdAt (DateTime, default now), updatedAt (DateTime, updatedAt).  
  2. Add the foreign key userId (String) and the relation user User @relation(fields: \[userId\], references: \[id\], onDelete: Cascade) to link cards to users (**KC-3.1** dependency). Ensure onDelete: Cascade.  
  3. Add the placeholder relation tags Tag\[\] @relation("CardToTag") (Tag model defined in **KC-20.2**).  
  4. Add the optional foreign key folderId (String?) and relation folder Folder? @relation(fields: \[folderId\], references: \[id\], onDelete: SetNull) (Folder model defined later in KC-ORG). Ensure onDelete: SetNull.  
  5. Add indexes: @@index(\[userId\]), @@index(\[folderId\]).  
  6. Run npx prisma migrate dev \--name add-card-model-json-content.  
  7. Run npx prisma generate.  
  8. Verify the Card type in the generated Prisma Client includes content: Prisma.JsonValue.

**3\. Ticket: KC-20.2: Define Tag Schema in Prisma**

* **Prompt:** Update the Prisma schema (prisma/schema.prisma) to define the Tag model and its many-to-many relationship with Card, as specified in **JIRA Ticket KC-20.2**.  
  1. Define model Tag with fields: id (String, cuid, id), name (String, unique).  
  2. Add the relation field cards Card\[\] @relation("CardToTag").  
  3. Ensure the corresponding tags Tag\[\] @relation("CardToTag") field exists in the Card model (**KC-20.1-BLOCK**). Prisma implicitly handles the \_CardToTag relation table.  
  4. Run npx prisma migrate dev \--name add-tag-model.  
  5. Run npx prisma generate.  
  6. *Note:* The @unique constraint on name is likely case-sensitive by default. Case-insensitive logic will be handled in **KC-25.1**.

**4\. Ticket: KC-25.1: Implement Robust Tag Handling (Find-or-Create)**

* **Prompt:** Implement a reusable backend function to handle case-insensitive finding or creation of tags for card upserts, as specified in **JIRA Ticket KC-25.1**.  
  1. Create src/lib/tags.ts.  
  2. Export async function getTagConnectionsForUpsert(tagNames: string\[\]): Promise\<{ connectOrCreate: { where: { name: string }, create: { name: string } }\[\] }\>.  
  3. Inside the function:  
     * Normalize input: tagNames.map(n \=\> n.trim().toLowerCase()).filter(Boolean).  
     * Get unique names: \[...new Set(normalizedNames)\]. Return \[\] if empty.  
     * Fetch existing tags matching unique lowercase names case-insensitively:  
       * **Primary approach:** await prisma.tag.findMany({ where: { name: { in: uniqueNames, mode: 'insensitive' } } }); (Requires DB support like PostgreSQL).  
       * **Fallback (if insensitive mode not reliable/supported):** Fetch potential matches by lowercase/original case and filter in application code using a Map keyed by lowercase name.  
     * Map unique lowercase names to Prisma connectOrCreate input format:  
       * For each name, check if a corresponding tag exists in the fetched existingTags (case-insensitive lookup).  
       * Determine the canonicalName (use the exact name from the existing tag if found, otherwise use the normalized lowercase name).  
       * Return { where: { name: canonicalName }, create: { name: canonicalName } }.  
  4. Write comprehensive unit tests for getTagConnectionsForUpsert in src/lib/tags.test.ts, mocking Prisma calls and covering all scenarios (empty input, new tags, existing tags \- various casings, mixed, duplicates, case-sensitive/insensitive DB simulation).

**5\. Ticket: KC-CARD-FE-7-BLOCK: Implement Reusable Tag Input Component**

* **Prompt:** Create the reusable TagInput frontend component as specified in **JIRA Ticket KC-CARD-FE-7-BLOCK**.  
  1. Create src/components/tags/TagInput.tsx. Mark as 'use client'.  
  2. Use Chakra UI: FormControl, FormLabel, Input, Box, Tag, TagLabel, TagCloseButton, Wrap.  
  3. Props: interface TagInputProps { value: string\[\]; onChange: (tags: string\[\]) \=\> void; placeholder?: string; isDisabled?: boolean; }.  
  4. State: useState for inputValue: string and internal tags: string\[\] (synced with props.value).  
  5. Input onKeyDown: Handle Enter and ,. Trim inputValue. If valid and not a duplicate (case-insensitive check against tags), add to tags state, clear inputValue, and call props.onChange with the new array. Prevent default if necessary.  
  6. Input onChange: Update inputValue state.  
  7. Render tags state as Chakra Tag components inside Wrap. Each Tag needs a TagCloseButton with onClick to remove the tag and call props.onChange.  
  8. Implement case-insensitive duplicate check before adding.  
  9. Style according to **KC-CARD-UX-1-BLOCK** design and **UI Style Guide**.  
  10. Write unit tests (src/components/tags/TagInput.test.tsx) covering adding (Enter/Comma), removing, duplicate prevention, onChange callback, and initial value prop.

**6\. Ticket: KC-CARD-FE-1-BLOCK: Implement Block Editor Frontend Component**

* **Prompt:** Create the reusable BlockEditor React component wrapping BlockNote.js as specified in **JIRA Ticket KC-CARD-FE-1-BLOCK**.  
  1. Create src/components/editor/BlockEditor.tsx. Mark as 'use client'.  
  2. Import BlockNoteView, useBlockNote from @blocknote/react and BlockNoteEditor, PartialBlock from @blocknote/core.  
  3. Props: interface BlockEditorProps { initialContent?: PartialBlock\[\]; onChange: (blocks: PartialBlock\[\]) \=\> void; editable?: boolean; }. Default editable to true.  
  4. Editor instance: const editor \= useBlockNote({ initialContent: props.initialContent, onEditorContentChange: (editor) \=\> { props.onChange(editor.topLevelBlocks); }, ... });. Ensure default blocks (Paragraph, Headings, Lists) are enabled. Configure slash commands.  
  5. Render: \<BlockNoteView editor={editor} editable={props.editable} theme="light" /\> (or appropriate theme).  
  6. **Styling:** Import BlockNote CSS (@import "@blocknote/core/style.css";). Customize theme variables or override CSS classes to match **KC-CARD-UX-1-BLOCK** design and Chakra UI theme. Refer to BlockNote theming docs.  
  7. Write unit tests (src/components/editor/BlockEditor.test.tsx) checking rendering, initialContent propagation, editable prop effect, and onChange callback firing.

**7\. Ticket: KC-23-BLOCK: Create API endpoint to Create Card with JSON Content**

* **Prompt:** Implement the POST /api/cards endpoint to create new cards as specified in **JIRA Ticket KC-23-BLOCK**.  
  1. Create app/api/cards/route.ts. Export async POST(request: Request).  
  2. Import NextResponse, prisma, getCurrentUserId (**KC-8.2**), getTagConnectionsForUpsert (**KC-25.1**), zod.  
  3. Define CreateCardSchema \= z.object({ title: z.string().min(1), content: z.array(z.any()).min(1), tags: z.array(z.string()).optional(), folderId: z.string().cuid().optional().nullable() });. *Consider if more specific content validation is feasible.*  
  4. Auth check: const userId \= await getCurrentUserId(); if (\!userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });.  
  5. Parse and validate body: const validation \= CreateCardSchema.safeParse(await request.json()); if (\!validation.success) return NextResponse.json({ errors: validation.error.format() }, { status: 400 });.  
  6. Prepare prismaData: { title, content, userId, folderId } from validation.data.  
  7. Handle tags: If validation.data.tags exists, call getTagConnectionsForUpsert and set prismaData.tags \= { connectOrCreate: tagConnections };.  
  8. Use try/catch for prisma.card.create({ data: prismaData, include: { tags: true, folder: true } });.  
  9. On success, return NextResponse.json(newCard, { status: 201 });.  
  10. Handle Prisma/other errors (500).  
  11. Write integration tests (**KC-CARD-TEST-BE-1-BLOCK**) covering success, validation errors, auth errors, tag handling, and DB errors.

**8\. Ticket: KC-CARD-FE-2-BLOCK: Implement Card Creation Page UI & Logic**

* **Prompt:** Implement the card creation page UI and logic as specified in **JIRA Ticket KC-CARD-FE-2-BLOCK**.  
  1. Create src/app/(protected)/cards/new/page.tsx. Mark as 'use client'. Wrap route/layout with AuthGuard (**KC-AUTH-FE-4**).  
  2. Import useState, BlockEditor (**KC-CARD-FE-1-BLOCK**), TagInput (**KC-CARD-FE-7-BLOCK**), useRouter, useToast, Chakra components.  
  3. State: title, content: PartialBlock\[\], tags: string\[\], isLoading, apiError.  
  4. Render form: Input for title, BlockEditor (onChange={setContent}), TagInput (value={tags}, onChange={setTags}), "Save Card" Button (onClick={handleSaveCard}, isLoading).  
  5. Implement handleSaveCard:  
     * Client validation (e.g., title empty).  
     * Set loading/reset error state.  
     * fetch('/api/cards', { method: 'POST', ..., body: JSON.stringify({ title, content, tags }) }).  
     * On success (201): Parse response (newCard), show success toast, router.push(\\/cards/${newCard.id}\`)\`.  
     * On failure: Parse error, set apiError, show error toast.  
     * Handle fetch errors. Use finally to reset loading state.  
  6. Display apiError if present.  
  7. Style according to **KC-CARD-UX-1-BLOCK** design.  
  8. Write integration tests (**KC-CARD-TEST-FE-1-BLOCK**) covering successful creation, validation errors, API errors, and redirection.

**9\. Ticket: KC-CARD-BE-1-BLOCK: Create API endpoint to fetch a single card**

* **Prompt:** Implement the GET /api/cards/{cardId} endpoint to fetch a single card with ownership check, as specified in **JIRA Ticket KC-CARD-BE-1-BLOCK**.  
  1. Create app/api/cards/\[cardId\]/route.ts. Export async GET(request: Request, { params }: { params: { cardId: string } }).  
  2. Import NextResponse, prisma, getCurrentUserId.  
  3. Validate params.cardId format (e.g., CUID check). Return 400 if invalid.  
  4. Auth check: const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }.  
  5. Use try/catch for prisma.card.findUnique({ where: { id: params.cardId, userId: userId }, include: { tags: true, folder: true } });. **Crucially include userId in the where clause.**  
  6. If \!card, return NextResponse.json({ error: 'Card not found' }, { status: 404 });.  
  7. On success, return NextResponse.json(card);.  
  8. Handle Prisma/other errors (500).  
  9. Write integration tests (**KC-CARD-TEST-BE-1-BLOCK**) covering success, not found (wrong ID or wrong user), auth error, invalid ID format.

**10\. Ticket: KC-CARD-FE-3-BLOCK: Implement Card Display Page UI**

* **Prompt:** Implement the card display page UI as specified in **JIRA Ticket KC-CARD-FE-3-BLOCK**.  
  1. Create src/app/(protected)/cards/\[cardId\]/page.tsx. Mark as 'use client'. Wrap route/layout with AuthGuard.  
  2. Import useEffect, useState, useParams, BlockEditor (**KC-CARD-FE-1-BLOCK**), Chakra components, Link from next/link.  
  3. State: cardData: Card | null, isLoading, error.  
  4. Get cardId from useParams().  
  5. useEffect: Fetch data from /api/cards/${cardId} when cardId changes. Handle loading state. Set cardData on success. Handle errors (404, 401/403, 500\) by setting error state.  
  6. Render: Loading indicator, error message, or card details.  
  7. If cardData: Display cardData.title, map cardData.tags to Chakra Tag components, render \<BlockEditor initialContent={cardData.content as PartialBlock\[\]} editable={false} onChange={() \=\> {}} /\>. Add "Edit" Link (/cards/${cardId}/edit) and "Delete" Button (logic in **KC-CARD-FE-5-BLOCK**).  
  8. Style according to **KC-CARD-UX-1-BLOCK** design (read-only view).  
  9. Write integration tests (**KC-CARD-TEST-FE-1-BLOCK**) covering data fetching, loading/error states, rendering title/tags/read-only content, and presence of Edit/Delete buttons.

**11\. Ticket: KC-CARD-BE-2-BLOCK: Create API endpoint to update a card**

* **Prompt:** Implement the PUT /api/cards/{cardId} endpoint to update cards with ownership check, as specified in **JIRA Ticket KC-CARD-BE-2-BLOCK**.  
  1. In app/api/cards/\[cardId\]/route.ts, export async PUT(request: Request, { params }: { params: { cardId: string } }).  
  2. Import NextResponse, prisma, getCurrentUserId, getTagConnectionsForUpsert, zod.  
  3. Validate params.cardId format (400 if invalid).  
  4. Auth check: const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }.  
  5. Define UpdateCardSchema \= CreateCardSchema.partial(); (**KC-23-BLOCK** schema).  
  6. Parse and validate body: const validation \= UpdateCardSchema.safeParse(await request.json()); if (\!validation.success) { /\* 400 \*/ }.  
  7. Use try/catch.  
  8. **Ownership check:** const existingCard \= await prisma.card.findUnique({ where: { id: params.cardId, userId: userId } }); if (\!existingCard) { /\* 404 \*/ }.  
  9. Prepare prismaUpdateData: Include fields (title, content, folderId) only if present in validation.data.  
  10. Handle tags: If validation.data.tags is present (can be empty array), call getTagConnectionsForUpsert and set prismaUpdateData.tags \= { set: \[\], connectOrCreate: tagConnections }; (**Disconnect all existing tags first**).  
  11. const updatedCard \= await prisma.card.update({ where: { id: params.cardId }, data: prismaUpdateData, include: { tags: true, folder: true } });.  
  12. Return NextResponse.json(updatedCard);.  
  13. Handle Prisma/other errors (500).  
  14. Write integration tests (**KC-CARD-TEST-BE-1-BLOCK**) covering success (updating various fields), validation, ownership check failure, auth error, tag replacement logic.

**12\. Ticket: KC-CARD-FE-4-BLOCK: Implement Card Editing Page UI & Logic**

* **Prompt:** Implement the card editing page UI and logic as specified in **JIRA Ticket KC-CARD-FE-4-BLOCK**.  
  1. Create src/app/(protected)/cards/\[cardId\]/edit/page.tsx. Mark as 'use client'. Wrap route/layout with AuthGuard.  
  2. Import useEffect, useState, useParams, BlockEditor, TagInput, useRouter, useToast, Chakra components.  
  3. State: initialData: Card | null, title, content, tags, isLoading, isUpdating, error.  
  4. Get cardId from useParams().  
  5. useEffect: Fetch initial data from /api/cards/${cardId}. Set initialData and populate form state (setTitle, setContent, setTags) on success. Handle loading/error states for fetch.  
  6. Render form similar to Create Page, but pre-populate Input, BlockEditor (initialContent), and TagInput (value) from state. Use "Update Card" button text.  
  7. Implement handleUpdateCard:  
     * Set isUpdating state.  
     * fetch(\\/api/cards/${cardId}\`, { method: 'PUT', ..., body: JSON.stringify({ title, content, tags }) })\`.  
     * On success (200): Show success toast, router.push(\\/cards/${cardId}\`)\`.  
     * On failure: Parse error, set error state, show error toast.  
     * Use finally to reset isUpdating state.  
  8. Handle loading/error states for both initial fetch and update action.  
  9. Style according to **KC-CARD-UX-1-BLOCK** design.  
  10. Write integration tests (**KC-CARD-TEST-FE-1-BLOCK**) covering fetching data, pre-populating form, successful update, handling fetch/update errors, redirection.

**13\. Ticket: KC-CARD-BE-3-BLOCK: Create API endpoint to delete a card**

* **Prompt:** Implement the DELETE /api/cards/{cardId} endpoint to delete cards with ownership check, as specified in **JIRA Ticket KC-CARD-BE-3-BLOCK**.  
  1. In app/api/cards/\[cardId\]/route.ts, export async DELETE(request: Request, { params }: { params: { cardId: string } }).  
  2. Import NextResponse, prisma, getCurrentUserId.  
  3. Validate params.cardId format (400 if invalid).  
  4. Auth check: const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }.  
  5. Use try/catch.  
  6. **Ownership check:** const existingCard \= await prisma.card.findUnique({ where: { id: params.cardId, userId: userId }, select: { id: true } }); if (\!existingCard) { /\* 404 \*/ }.  
  7. await prisma.card.delete({ where: { id: params.cardId } });.  
  8. Return NextResponse.json({ message: 'Card deleted' }, { status: 200 }); or NextResponse.next({ status: 204 });.  
  9. Handle Prisma/other errors (500).  
  10. Write integration tests (**KC-CARD-TEST-BE-1-BLOCK**) covering success, not found (wrong ID or wrong user), auth error, invalid ID format.

**14\. Ticket: KC-CARD-FE-5-BLOCK: Implement Card Deletion UI Logic**

* **Prompt:** Implement the card deletion UI logic (confirmation dialog) as specified in **JIRA Ticket KC-CARD-FE-5-BLOCK**.  
  1. Modify the card display page (src/app/(protected)/cards/\[cardId\]/page.tsx from **KC-CARD-FE-3-BLOCK**).  
  2. Import useDisclosure, AlertDialog, related Chakra components, Button, useToast, useRouter.  
  3. State: isDeleting. Use useDisclosure for dialog state (isOpen, onOpen, onClose).  
  4. Add onClick={onOpen} to the "Delete" button.  
  5. Render AlertDialog controlled by isOpen. Include header, body ("Are you sure?"), and footer with "Cancel" (onClose) and "Delete" (onClick={handleDeleteConfirm}, isLoading={isDeleting}, colorScheme='red') buttons.  
  6. Implement handleDeleteConfirm:  
     * Set isDeleting(true).  
     * fetch(\\/api/cards/${cardId}\`, { method: 'DELETE' })\`.  
     * On success (200/204): Show success toast, router.push('/dashboard') (or card list).  
     * On failure: Show error toast.  
     * Use finally to setIsDeleting(false) and onClose().  
  7. Write integration tests (**KC-CARD-TEST-FE-1-BLOCK**) covering opening dialog, confirming deletion (mocking fetch, toast, router), cancelling deletion.

**15\. Ticket: KC-CARD-BE-4-BLOCK: Create API endpoint to list user's cards**

* **Prompt:** Implement the GET /api/cards endpoint to list the user's cards as specified in **JIRA Ticket KC-CARD-BE-4-BLOCK**.  
  1. In app/api/cards/route.ts, export async GET(request: Request).  
  2. Import NextResponse, prisma, getCurrentUserId.  
  3. Auth check: const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }.  
  4. Use try/catch.  
  5. const cards \= await prisma.card.findMany({ where: { userId: userId }, select: { id: true, title: true, updatedAt: true, tags: { select: { name: true }, take: 3 } }, orderBy: { updatedAt: 'desc' } });. Select only necessary fields for list view.  
  6. Return NextResponse.json(cards);.  
  7. Handle Prisma/other errors (500).  
  8. Write integration tests (**KC-CARD-TEST-BE-1-BLOCK**) covering success (with/without cards), auth error, verifying selected fields and default sorting.

**16\. Ticket: KC-CARD-FE-6-BLOCK: Implement Basic Card List UI**

* **Prompt:** Implement the basic card list UI (e.g., on dashboard) as specified in **JIRA Ticket KC-CARD-FE-6-BLOCK**.  
  1. Create/Modify src/app/(protected)/dashboard/page.tsx (or similar). Mark as 'use client'. Wrap route/layout with AuthGuard.  
  2. Import useEffect, useState, Chakra components (Box, VStack, Heading, Text, Spinner, Link as ChakraLink, Button), Link from next/link.  
  3. State: cards: CardListItem\[\], isLoading, error. Define CardListItem type based on API response (**KC-CARD-BE-4-BLOCK**).  
  4. useEffect: Fetch data from /api/cards. Handle loading/error states. Set cards on success.  
  5. Render: Loading indicator, error message, or card list.  
  6. If cards.length \=== 0, show "No cards" message and "Create New Card" link/button.  
  7. If cards.length \> 0, map cards to list items (Box or similar). Each item should be wrapped in \<Link href={\\/cards/${card.id}\`} passHref\>.... Display card.title, formatted card.updatedAt, and maybe first few card.tags\`.  
  8. Include a prominent "Create New Card" button/link on the page.  
  9. Style according to **UI Style Guide**.  
  10. Write integration tests (**KC-CARD-TEST-FE-1-BLOCK**) covering data fetching, loading/error states, empty list state, rendering list items with links, and presence of create button.

**17\. Ticket: KC-CARD-TEST-BE-1-BLOCK: Write Unit Tests for Card CRUD API Logic**

* **Prompt:** Write comprehensive unit/integration tests for the Card CRUD API endpoints using Jest/Vitest as specified in **JIRA Ticket KC-CARD-TEST-BE-1-BLOCK**.  
  1. Create test files (e.g., tests/integration/api/cards/route.test.ts, tests/integration/api/cards/\[cardId\]/route.test.ts).  
  2. Mock prisma client methods (create, findUnique, findMany, update, delete), getCurrentUserId, getTagConnectionsForUpsert.  
  3. **POST /api/cards:** Test success (201), validation errors (400), auth errors (401), tag logic called.  
  4. **GET /api/cards:** Test success (200, empty/non-empty list), auth errors (401), correct fields selected, default sort order.  
  5. **GET /api/cards/{cardId}:** Test success (200), ownership check (404 for wrong user), not found (404), auth error (401), invalid ID (400).  
  6. **PUT /api/cards/{cardId}:** Test success (200), validation errors (400), ownership check (404), auth error (401), tag replacement logic (set: \[\], connectOrCreate).  
  7. **DELETE /api/cards/{cardId}:** Test success (200/204), ownership check (404), auth error (401), invalid ID (400).  
  8. Follow testing practices from **Testing Strategy Section 2.1/2.2** and **Coding Standards Section 4.5**. Reset mocks beforeEach.

**18\. Ticket: KC-CARD-TEST-FE-1-BLOCK: Write Unit Tests for Card Frontend Components**

* **Prompt:** Write unit tests for the key Card frontend components using Jest and React Testing Library as specified in **JIRA Ticket KC-CARD-TEST-FE-1-BLOCK**.
  1. Create test files alongside components (BlockEditor.test.tsx, TagInput.test.tsx, pages/cards/new/page.test.tsx, etc.).
  2. Mock fetch, next/navigation (useRouter, useParams), @chakra-ui/react (useToast), next-auth/react (useSession).
  3. **BlockEditor:** Test rendering, props (initialContent, editable), onChange callback.
  4. **TagInput:** Test adding (Enter/Comma), removing, duplicates, onChange, value prop.
  5. **Create/Edit Pages:** Test form rendering, state changes, submit handler logic (mocking fetch, router, toast), error handling, pre-population (edit).
  6. **Display Page:** Test data fetching (useEffect, mock fetch/useParams), rendering based on fetch state (loading, error, success), rendering read-only content.
  7. **List Page:** Test data fetching (useEffect, mock fetch), rendering based on fetch state (loading, error, empty, list), rendering card links.
  8. **Delete Logic (in Display Page):** Test dialog opening, confirm action (mock fetch, toast, router), cancel action.
  9. Follow testing practices from **Testing Strategy Section 2.1/2.2** and **Coding Standards Section 5.4**. Use renderWithProviders test utility.

**19\. Ticket: KC-CARD-FE-8: Display Folder Name on Card List Items [Implemented]**

*   **Epic:** KC-CARD-CREATE / KC-ANALYTICS (UI Aspect)
*   **PRD Requirement(s):** Implied Usability Enhancement
*   **Team:** FE / BE
*   **Dependencies (Functional):** KC-CARD-FE-6-BLOCK (Basic Card List UI), KC-CARD-BE-4-BLOCK (List Cards API), KC-ORG (Folders exist)
*   **UX/UI Design Link:** \[Link to updated Figma/mockups showing folder name on card] (Requires UX input)
*   **Description (Functional):** When viewing the list of cards (e.g., on the dashboard or main view at /), display the name of the folder that each card belongs to, if any. This provides users with immediate context about the card's organization.
*   **Acceptance Criteria (Functional):**
    *   The API endpoint for listing cards (GET /api/cards) includes the ID and name of the folder each card belongs to (if assigned).
    *   The frontend component displaying the list of cards (e.g., CardListItem used in the dashboard) renders the folder name visually associated with the card item (e.g., below the title, as a badge).
    *   Cards not assigned to any folder do not display a folder name.
    *   The display matches the updated UX design.
*   **Technical Approach / Implementation Notes (AI-Friendly Prompt):**
    *   **Backend (KC-CARD-BE-4-BLOCK Revision):**
        *   Modify the Prisma query within the GET `/api/cards` route handler (`app/api/cards/route.ts`).
        *   Update the Prisma query to `include` the related folder's `id` and `name`:
            ```prisma
            // Inside prisma.knowledgeCard.findMany call:
            include: {
              folder: {
                select: {
                  id: true,   // Ensure ID is included
                  name: true
                }
              }
              // tags: { select: { name: true }, take: 3 }, // Example if tags are needed
            }
            ```
        *   Ensure the API response structure now includes the `folder: { id: string, name: string } | null` field for each card. Update `CardListItem` interface in `src/stores/cardStore.ts`.
    *   **Frontend (KC-CARD-FE-6-BLOCK Revision or KC-CARD-FE-8-BLOCK if refactored):**
        *   Update the frontend type/interface used for card list items (`CardListItem` in `src/stores/cardStore.ts`) to include the optional `folder` object with `id` and `name`.
        *   Modify the React component responsible for rendering individual card items in the list (e.g., `src/app/page.tsx` or `src/components/CardList.tsx`).
        *   Within the component, check if `card.folder?.name` exists.
        *   If present, render it using a suitable Chakra UI component (e.g., a small `Text` component, possibly with an icon, or a `Badge`) in the location specified by the UX design. Example:
            ```tsx
            // Inside CardBody:
            {card.folder?.name && (
              <Flex align="center" mt={1} opacity={0.7}>
                 {/* Optional: <Icon as={FolderIcon} mr={1} /> */}
                <Text fontSize="xs" ml={1}>
                  {card.folder.name}
                </Text>
              </Flex>
            )}
            ```
        *   Ensure the layout remains clean.
*   **API Contract (if applicable):** Modifies response of `GET /api/cards`. Adds `folder: { id: string, name: string } | null` to each card object in the response array.
*   **Data Model Changes (if applicable):** N/A (Uses existing relation)
*   **Key Functions/Modules Involved:**
    *   `app/api/cards/route.ts` (GET handler)
    *   Frontend card list component (`src/app/page.tsx` or `src/components/CardList.tsx`)
    *   `src/stores/cardStore.ts` (`CardListItem` interface)
    *   Prisma Client (`findMany` with `include`)
    *   Chakra UI components (`Text`, `Badge`, `Flex`, `Icon`?)
*   **Testing Considerations (Technical):** Update backend tests for `GET /api/cards` to verify the folder field (id and name) is included/excluded correctly. Update frontend unit tests for the card list item to check for folder name rendering. E2E test the dashboard view to confirm folder names appear correctly.
*   **Dependencies (Technical):** `KC-CARD-BE-4-BLOCK`, `KC-CARD-FE-6-BLOCK` / `KC-CARD-FE-8-BLOCK`

**20\. Ticket: KC-ORG-FE-8: Display Card Count in Folder Tree [Implemented]**

*   **Epic:** KC-ORG
*   **PRD Requirement(s):** Implied Usability Enhancement
*   **Team:** FE / BE
*   **Dependencies (Functional):** KC-ORG-FE-1 (Folder Tree Display), KC-ORG-BE-1 (List Folders API)
*   **UX/UI Design Link:** \[Link to updated Figma/mockups showing count in folder tree] (Requires UX input)
*   **Description (Functional):** Enhance the folder tree display in the sidebar to show the number of cards contained within each folder directly next to the folder name, ensuring the count is visible even if the folder name is long.
*   **Acceptance Criteria (Functional):**
    *   The API endpoint for listing folders (GET /api/folders) includes the count of cards directly associated with each folder.
    *   The frontend `FolderTree` component displays this count next to each folder name (e.g., in parentheses or a badge).
    *   If a folder name is too long for the available space, it is truncated (e.g., with an ellipsis) to ensure the card count remains visible.
    *   Folders containing zero cards display "0" or omit the count based on UX design.
    *   The count reflects only cards directly within that folder, not recursively including cards in sub-folders (for Stage 1 simplicity).
    *   *(Implicitly Fixed):* The count updates correctly after a card is moved into or out of a folder.
*   **Technical Approach / Implementation Notes (AI-Friendly Prompt):**
    *   **Backend (KC-ORG-BE-1 Revision):**
        *   Modify the Prisma query within the `GET /api/folders` route handler (`app/api/folders/route.ts`).
        *   Update the query to include a count of related cards using Prisma's `_count` feature:
            ```prisma
            // Inside prisma.folder.findMany call:
            select: {
              id: true,
              name: true,
              parentId: true,
              updatedAt: true,
              _count: { // Add this block
                select: {
                  cards: true // Select the count of related cards
                }
              }
            }
            ```
        *   Ensure the API response structure now includes the `_count: { cards: number }` field for each folder. Update corresponding backend types/interfaces (`FolderWithCount`?).
    *   **Frontend (KC-ORG-FE-1 / FolderTreeNode Revision):**
        *   Update the frontend type/interface used for folder data (`FolderListItem` in `src/lib/folderUtils.ts`) to include the optional `_count: { cards: number }` field.
        *   Modify the React component rendering individual folder nodes (`src/components/folders/FolderTreeNode.tsx`).
        *   Change the `HStack` containing the folder name and action buttons to structure the name and count separately, allowing the name to truncate.
        *   Use a `Flex` container with `justifyContent="space-between"` and `alignItems="center"` within the main `HStack` (replacing the simple `Text` for the name).
        *   Inside the `Flex`, render the folder name using `Text` with `noOfLines={1}` and `title={node.name}`. Wrap this `Text` in a `Box` with `flex="1"` and `overflow="hidden"` to allow it to take available space and truncate.
        *   Render the count (`node._count?.cards`) next to the name container (still inside the `Flex`) using a suitable component like `Badge` or `Text`, ensuring it doesn't shrink (`flexShrink={0}`).
            ```tsx
             // Inside the main HStack, replace the <Text>{node.name}</Text>:
             <Flex flex={1} align="center" overflow="hidden" mr={1}> {/* Allow flex grow, hide overflow */}
               <Text fontSize="sm" noOfLines={1} title={node.name} > {/* Truncate name */}
                 {node.name}
               </Text>
             </Flex>
             {/* Display Card Count */}
             {typeof node._count?.cards === 'number' && (
               <Badge
                 fontSize="0.7em"
                 colorScheme="gray"
                 variant="subtle"
                 flexShrink={0} // Prevent count from shrinking
                 px={1.5} // Add some padding
                 borderRadius="sm" // Optional styling
               >
                 {node._count.cards}
               </Badge>
             )}
             {/* Spacer might be needed before action buttons depending on layout */}
             <Spacer />
             {/* Action Buttons (Edit/Delete) */}
            ```
        *   Adjust spacing (`mr`, `ml`, `px`) and ensure the expand/collapse icon and action buttons remain correctly positioned within the main `HStack`.
    *   **API Contract (if applicable):** Modifies response of `GET /api/folders`. Adds `_count: { cards: number }` to each folder object in the response array.
    *   **Data Model Changes (if applicable):** N/A (Uses existing relation)
    *   **Key Functions/Modules Involved:**
        *   `app/api/folders/route.ts` (GET handler)
        *   `src/components/folders/FolderTreeNode.tsx`
        *   `src/lib/folderUtils.ts` (`FolderListItem` interface)
        *   Prisma Client (`findMany` with `_count`)
        *   Chakra UI components (`Text`, `Badge`, `Flex`, `Box`)
    *   **Testing Considerations (Technical):** Update backend tests for `GET /api/folders`. Update frontend unit tests for `FolderTreeNode` for count rendering and name truncation. E2E test with short/long names.
    *   **Dependencies (Technical):** `KC-ORG-BE-1`, `KC-ORG-FE-1`

**21\. Ticket: KC-ORG-FE-10: Ensure Card Data Includes Current Folder Info for Move Confirmation [Implemented]**

*   **Epic:** KC-ORG / KC-CARD-CREATE
*   **PRD Requirement(s):** Implied by KC-ORG-FE-9
*   **Team:** FE / BE
*   **Dependencies (Functional):** KC-CARD-FE-8 (API includes folder data), KC-CARD-FE-6-BLOCK (Card List UI)
*   **UX/UI Design Link:** N/A
*   **Description (Functional):** Ensure that the frontend component responsible for handling card move operations (e.g., the card list where dragging originates) has access to the `folderId` and `folderName` of the card being moved *before* the move is initiated. This data is needed to display the correct confirmation message in `KC-ORG-FE-9`.
*   **Acceptance Criteria (Functional):**
    *   The data structure representing a card within the frontend card list component includes `folder: { id: string, name: string } | null`. (Covered by KC-CARD-FE-8 changes).
    *   When a drag operation (or other move initiation) starts for a card, its current `folder.id` and `folder.name` (or null if unassigned) are readily accessible to the event handler managing the move/drop confirmation logic.
*   **Technical Approach / Implementation Notes (AI-Friendly Prompt):**
    *   **Verify API Response:** Confirm that the backend API (`GET /api/cards`, modified by `KC-CARD-FE-8`) correctly returns the `folder { id, name }` object (or `null`) for each card. *(This should already be the case after implementing KC-CARD-FE-8)*.
    *   **Update Frontend Types:** Ensure the TypeScript type/interface used for cards in the frontend state (e.g., `CardListItem` in `src/stores/cardStore.ts`) includes the optional `folder` object with `id` and `name`. *(This should also be the case after implementing KC-CARD-FE-8, but verify `id` is included if needed)*.
    *   **Data Fetching/Storage:** Verify the data fetching logic (`fetchCards` in `src/stores/cardStore.ts` and its usage in `src/app/page.tsx`) stores the full card objects received from the API, including the folder details, in the store's state.
    *   **Access Data During Move:** Ensure the component handling the drag start (`DraggableCardItem` in `src/components/dnd/DraggableCardItem.tsx`) includes the necessary card data (including `folder` info) in its `data` payload for the `useDraggable` hook. This makes the data available in the `active` object within the `onDragEnd` handler in `Layout.tsx`.
        ```tsx
        // In DraggableCardItem.tsx
        const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
          id: card.id, // Pass the full card object, not just id
          data: { type: 'card', cardData: card } // Pass the full card object in data
        });

        // In Layout.tsx onDragEnd handler
        const draggedCardData = active.data.current?.cardData as CardListItem | undefined;
        const currentFolderId = draggedCardData?.folderId;
        const currentFolderName = draggedCardData?.folder?.name;
        ```
*   **API Contract (if applicable):** Relies on the modified response from `GET /api/cards` (as defined in `KC-CARD-FE-8`).
*   **Data Model Changes (if applicable):** N/A
*   **Key Functions/Modules Involved:**
    *   `src/app/api/cards/route.ts` (GET handler)
    *   `src/stores/cardStore.ts` (`CardListItem` interface, `fetchCards` logic)
    *   `src/app/page.tsx` (Card list rendering and data usage)
    *   `src/components/dnd/DraggableCardItem.tsx` (`useDraggable` hook setup)
    *   `src/components/layout/Layout.tsx` (`onDragEnd` handler access to `active.data`)
    *   TypeScript interfaces for card data.
*   **Testing Considerations (Technical):** Update unit tests for `DraggableCardItem` to ensure `cardData` is passed correctly. Verify during E2E testing of `KC-ORG-FE-9` that the correct current folder name is retrieved and displayed in the confirmation dialog.
*   **Dependencies (Technical):** `KC-CARD-FE-8` (ensures API provides the data), `KC-CARD-FE-6-BLOCK` (where data is fetched/stored), `DraggableCardItem` component.

**22\. Ticket: KC-ORG-FE-9: Implement Confirmation Dialog for Moving Cards [Implemented]**

*   **Epic:** KC-ORG
*   **PRD Requirement(s):** Implied Usability Enhancement (Error Prevention)
*   **Team:** FE
*   **Dependencies (Functional):** KC-ORG-FE-6 (Move Card UI Logic - DND), KC-ORG-FE-10 (Card Folder Data Availability), KC-ORG-UX-1 (Confirmation Dialog Design - TBD)
*   **UX/UI Design Link:** \[Link to Figma/mockups for Move Card Confirmation Dialog] (Requires UX input for dialog appearance)
*   **Description (Functional):** Before executing the action to move a card to a different folder (or to/from the root level), present the user with a confirmation dialog displaying the intended move and require explicit confirmation.
*   **Acceptance Criteria (Functional):**
    *   When initiating a card move (dropping a card onto a folder/root area):
        *   If the card is currently unassigned (`currentFolderId` is `null`) and the target is a folder: A dialog asks "Move card \[Card Title] to folder \[Target Folder Name]?".
        *   If the card is assigned (`currentFolderId` exists) and the target is a different folder: A dialog asks "Move card \[Card Title] from folder \[Current Folder Name] to folder \[Target Folder Name]?".
        *   If the card is assigned (`currentFolderId` exists) and the target is the root level (`targetFolderId` is `null`): A dialog asks "Remove card \[Card Title] from folder \[Current Folder Name]?". *(Note: Moving to root needs a specific drop target implementation)*.
    *   Each dialog provides "Confirm" and "Cancel" options.
    *   Clicking "Confirm" proceeds with the original move logic (calling the API).
    *   Clicking "Cancel" aborts the move operation, leaving the card in its original location.
*   **Technical Approach / Implementation Notes (AI-Friendly Prompt):**
    *   **Modify `Layout.tsx`:**
        *   Import `useDisclosure`, `AlertDialog`, related components, `useState`.
        *   Add state variables to hold the details needed for the confirmed move: `const [moveDetails, setMoveDetails] = useState<{ cardId: string; cardTitle: string; targetFolderId: string | null; currentFolderId: string | null; currentFolderName: string | null; targetFolderName: string | null;} | null>(null);`
        *   Import `useFolderStore` to access folder data by ID.
        *   Use `const { isOpen, onOpen, onClose } = useDisclosure();` for the dialog.
    *   **Refactor `handleDragEnd` in `Layout.tsx`:**
        *   Inside the `if (isCard && isFolder)` block, *instead* of directly calling the `fetch` API:
            *   Retrieve `draggedCardData` (including `title`), `currentFolderId`, `currentFolderName` from `active.data.current` (requires `KC-ORG-FE-10`).
            *   Retrieve `targetFolderId` from `over.id`.
            *   Find `targetFolderName` from the `useFolderStore` state: `const folders = useFolderStore.getState().folders; const targetFolder = folders.find(f => f.id === targetFolderId); const targetFolderName = targetFolder?.name;`
            *   Store the necessary details for the move: `setMoveDetails({ cardId: active.id as string, cardTitle: draggedCardData?.title ?? 'this card', targetFolderId: over.id as string, currentFolderId: currentFolderId, currentFolderName: currentFolderName, targetFolderName: targetFolderName });`
            *   Open the dialog: `onOpen();`
    *   **Implement `confirmMove` function in `Layout.tsx`:**
        *   `const confirmMove = async () => { if (!moveDetails) return; const { cardId, targetFolderId } = moveDetails; onClose(); // Close dialog first`
        *   Place the existing `try/catch` block (containing the `fetch` PUT request to `/api/cards/{cardId}`, `fetchCards`, `fetchFolders`, and toasts) inside this `confirmMove` function, ensuring it uses `cardId` and `targetFolderId` from `moveDetails`.
        *   Call `confirmMove` from the "Confirm" button's `onClick`.
        *   Reset state after completion/error: `setMoveDetails(null);` in a `finally` block within `confirmMove`.
    *   **Render `AlertDialog` in `Layout.tsx`:**
        *   Add the `<AlertDialog>` component within the main return function of `Layout`.
        *   Conditionally render its content based on `moveDetails`.
        *   Dynamically set the `AlertDialogHeader` ("Confirm Move").
        *   Dynamically create the message for `AlertDialogBody` based on `moveDetails.currentFolderId`, `moveDetails.currentFolderName`, `moveDetails.targetFolderId`, `moveDetails.targetFolderName`, and `moveDetails.cardTitle` (implementing the logic from Acceptance Criteria).
        *   Add `AlertDialogFooter` with "Cancel" (`onClick={onClose}`) and "Confirm" (`onClick={confirmMove}`) buttons.
        *   *(Future: Implement root drop target and associated confirmation message)*
*   **API Contract (if applicable):** N/A (Frontend logic change)
*   **Data Model Changes (if applicable):** N/A
*   **Key Functions/Modules Involved:**
    *   `src/components/layout/Layout.tsx` (`handleDragEnd`, new `confirmMove`, state management)
    *   `src/stores/folderStore.ts` (Accessing folder names)
    *   Chakra UI `AlertDialog`, `useDisclosure`, `Button`.
    *   React `useState`.
*   **Testing Considerations (Technical):** Unit test the logic generating the dialog message. Unit test `confirmMove` (mocking fetch, stores, onClose). E2E test the drag-and-drop move for relevant scenarios, verifying dialog appearance, messages, and Confirm/Cancel actions.
*   **Dependencies (Technical):** `KC-ORG-FE-6` (existing DND), `KC-ORG-FE-10` (data availability).