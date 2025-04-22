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