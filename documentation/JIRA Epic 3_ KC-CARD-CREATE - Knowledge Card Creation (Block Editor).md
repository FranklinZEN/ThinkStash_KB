## **JIRA Epic: KC-CARD-CREATE \- Knowledge Card Creation (Block Editor Version \- Stage 1\)**

**Rationale:** Implement core card creation using a block editor with basic text blocks, storing data locally as JSON.

Ticket ID: KC-CARD-UX-1-BLOCK  
Title: Design Block Editor Experience & Core Blocks  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1  
Team: UX  
Dependencies (Functional): Decision on Block Editor Lib (KC-SETUP-3 \- BlockNote primary)  
UX/UI Design Link: \[Link to Figma/mockups\]  
Description (Functional): Design the user interface for creating and editing cards using a block-based approach (like Notion or Google Docs). Define how users interact with basic text blocks (Paragraphs, Headings, Lists) and apply simple formatting.  
Acceptance Criteria (Functional):

* Mockups show the editor within the card creation/editing page context (including Title input, Tag input, Save/Update button).  
* Mockups detail the visual appearance of Paragraph, H1, H2, H3, Bullet List, Numbered List blocks.  
* Designs specify how users create new blocks (e.g., pressing Enter, using a '+' button, or typing '/').  
* Designs show a floating toolbar or similar mechanism for applying Bold and Italic formatting to selected text.  
* Designs show how users change block types (e.g., Paragraph to Heading via toolbar or slash command).  
* Read-only appearance of these blocks is defined (for card display).  
* Designs are responsive and include detailed specs (spacing, typography, colors).  
  Technical Approach / Implementation Notes:  
* Base designs on BlockNote capabilities (review BlockNote docs/demos: https://www.blocknotejs.org/). Specify desired BlockNote theme/styling overrides to align with Chakra UI.  
* Define exact toolbar buttons needed (Bold, Italic, Block Type selector).  
* Define desired slash command interactions (e.g., /h1, /bulletList, /numberedList).  
* Ensure accessibility considerations (keyboard navigation for editor, focus states, ARIA attributes) are included.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved: N/A (Design artifact)  
  Testing Considerations (Technical): Usability testing on prototypes. Accessibility review of designs.  
  Dependencies (Technical): KC-SETUP-3 (BlockNote chosen)

Ticket ID: KC-20.1-BLOCK  
Title: Modify Card Schema for JSON Content  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1  
Team: BE  
Dependencies (Functional): KC-SETUP-2 (Prisma init), KC-3.1 (User model for relation)  
UX/UI Design Link: N/A  
Description (Functional): Update the database structure to store the rich card content from the block editor correctly, replacing simple text fields. Define the basic Card model.  
Acceptance Criteria (Functional):

* The database Card table can store a title, complex structured content (JSON), and associate with a User.  
* Timestamps for creation/update are recorded.  
  Technical Approach / Implementation Notes:  
* Edit prisma/schema.prisma. Define/Modify model Card:  
  model Card {  
    id        String   @id @default(cuid())  
    title     String  
    // Store BlockNote content as JSON. Use Json type (maps to jsonb in Postgres, TEXT in SQLite)  
    content   Json  
    createdAt DateTime @default(now())  
    updatedAt DateTime @updatedAt

    // Relation to User  
    userId    String  
    user      User     @relation(fields: \[userId\], references: \[id\], onDelete: Cascade) // Ensure cards are deleted if user is deleted

    // Relation to Tags (defined in KC-20.2)  
    tags      Tag\[\]    @relation("CardToTag")

    // Relation to Folder (defined in KC-ORG)  
    folderId  String?  
    folder    Folder?  @relation(fields: \[folderId\], references: \[id\], onDelete: SetNull) // If folder deleted, set card's folderId to null

    @@index(\[userId\]) // Index for fetching user's cards  
    @@index(\[folderId\]) // Index for fetching cards in a folder  
  }

* Run npx prisma migrate dev \--name add-card-model-json-content.  
* Run npx prisma generate.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): Creates/Modifies Card table. Changes content column type to Json. Adds relations and indexes.  
  Key Functions/Modules Involved:  
* prisma/schema.prisma  
* prisma/migrations/...  
  Testing Considerations (Technical): Verify migration applies cleanly. Verify Prisma Client types are updated (Card type includes content as Prisma.JsonValue).  
  Dependencies (Technical): KC-SETUP-2, KC-3.1

Ticket ID: KC-20.2  
Title: Define Tag Schema in Prisma  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-2  
Team: BE  
Dependencies (Functional): KC-20.1-BLOCK (Card model exists)  
UX/UI Design Link: N/A  
Description (Functional): Define the database structure for tags and establish a many-to-many relationship with cards, allowing multiple tags per card and reusing tags across cards.  
Acceptance Criteria (Functional):

* The database can store a list of unique tags (case-insensitive uniqueness preferred).  
* The system correctly tracks which tags are associated with which cards.  
* A single tag can be applied to multiple cards, and a single card can have multiple tags.  
  Technical Approach / Implementation Notes:  
* Edit prisma/schema.prisma.  
* Define model Tag:  
  model Tag {  
    id    String @id @default(cuid())  
    // Ensure uniqueness, potentially case-insensitive depending on DB collation or application logic  
    name  String @unique

    // Relation to Cards  
    cards Card\[\] @relation("CardToTag")

    // Optional: Relation to User if tags are user-specific (Not required for Stage 1\)  
    // userId String?  
    // user   User?   @relation(fields: \[userId\], references: \[id\])  
    // @@index(\[userId\])  
  }

* Ensure the corresponding relation field exists in model Card:  
  // Inside model Card  
  tags Tag\[\] @relation("CardToTag")

* Prisma implicitly handles the relation table (\_CardToTag).  
* Run npx prisma migrate dev \--name add-tag-model.  
* Run npx prisma generate.  
* Note on Case Insensitivity: Prisma @unique on String is typically case-sensitive at the DB level (depends on DB/collation). Case-insensitivity for tag matching/creation needs to be handled in application logic (see KC-25.1).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): Adds Tag table and the implicit \_CardToTag relation table. Adds tags relation field to Card.  
  Key Functions/Modules Involved:  
* prisma/schema.prisma  
* prisma/migrations/...  
  Testing Considerations (Technical): Verify migration applies. Test unique constraint on Tag.name (likely case-sensitive by default).  
  Dependencies (Technical): KC-20.1-BLOCK

Ticket ID: KC-25.1  
Title: Implement Robust Tag Handling (Find-or-Create)  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-2  
Team: BE  
Dependencies (Functional): KC-20.2 (Tag model exists)  
UX/UI Design Link: N/A  
Description (Functional): Implement backend logic to handle tag creation and association when saving cards. Ensure that tags are treated case-insensitively, existing tags are reused, and only genuinely new tags are created, preventing duplicates like "React" and "react".  
Acceptance Criteria (Functional):

* Adding tags like "React", "react", "REACT" to cards results in only one underlying "react" (or "React") tag being created/used.  
* The system correctly associates the canonical tag ID with the card.  
* New, unique tag names result in new tag records being created.  
* Empty or whitespace-only tag names are ignored.  
  Technical Approach / Implementation Notes:  
* Create lib/tags.ts. Export async function getTagConnectionsForUpsert(tagNames: string\[\]): Promise\<{ connectOrCreate: { where: { name: string }, create: { name: string } }\[\] }\>. (Using connectOrCreate is efficient for Prisma).  
* Inside the function:  
  * Normalize input: const normalizedNames \= tagNames.map(n \=\> n.trim().toLowerCase()).filter(Boolean); // Trim, lowercase, remove empty  
  * Get unique names: const uniqueNames \= \[...new Set(normalizedNames)\];  
  * If uniqueNames.length \=== 0, return \[\].  
  * **Crucially, handle case-insensitivity:** Since @unique might be case-sensitive, we fetch existing tags matching the lowercase names first to find the *canonical* casing stored in the DB.  
    * const existingTags \= await prisma.tag.findMany({ where: { name: { in: uniqueNames, mode: 'insensitive' } } }); // Use 'insensitive' if DB supports it (e.g., Postgres with citext or specific collation)  
    * **If DB doesn't support insensitive mode well (e.g., default SQLite):** Fetch potential matches and filter in code:  
      // Fallback for case-sensitive DBs  
      const potentialTags \= await prisma.tag.findMany({  
        where: { name: { in: uniqueNames.map(n \=\> n.toLowerCase()) } } // Query lowercase if stored lowercase  
        // OR query original casing if stored as created: where: { name: { in: uniqueNames } } and normalize later  
      });  
      const existingTagsMap \= new Map(potentialTags.map(t \=\> \[t.name.toLowerCase(), t\]));

  * Map unique lowercase names to Prisma connectOrCreate input format. For each name in uniqueNames:  
    * Find if it exists (case-insensitively) in existingTags (or existingTagsMap).  
    * If exists, use its exact DB name (existingTag.name) for both where.name and create.name to ensure consistency.  
    * If not exists, use the normalized lowercase name (name) for both where.name and create.name.  
  * Return the array of connectOrCreate objects.

// Example structure to return:  
// return uniqueNames.map(name \=\> {  
//   const existing \= /\* find existing tag logic \*/;  
//   const canonicalName \= existing ? existing.name : name; // Use existing casing or new lowercase  
//   return {  
//     where: { name: canonicalName },  
//     create: { name: canonicalName },  
//   };  
// });

* This helper function will be used in the Card Create (KC-23-BLOCK) and Update (KC-CARD-BE-2-BLOCK) APIs.  
  API Contract (if applicable): N/A (Internal library function)  
  Data Model Changes (if applicable): Potentially creates Tag records via the consuming API.  
  Key Functions/Modules Involved:  
* lib/tags.ts  
* Prisma Client (prisma.tag.findMany, potentially mode: 'insensitive')  
  Testing Considerations (Technical): Unit test getTagConnectionsForUpsert extensively: empty input, new tags, existing tags (various casings), mixed new/existing, duplicate inputs. Mock Prisma calls. Test with/without insensitive mode simulation.  
  Dependencies (Technical): KC-20.2

Ticket ID: KC-CARD-FE-7-BLOCK (Generated)  
Title: Implement Reusable Tag Input Component  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-2  
Team: FE  
Dependencies (Functional): KC-SETUP-3 (Chakra UI), KC-CARD-UX-1-BLOCK (Design)  
UX/UI Design Link: \[Link to Figma/mockups for Tag Input\]  
Description (Functional): Create a reusable frontend component that allows users to input multiple tags, displaying them visually (e.g., as pills) and providing the list of tag names to parent components.  
Acceptance Criteria (Functional):

* Component allows typing tag names into an input field.  
* Pressing Enter or comma adds the typed text as a tag "pill".  
* Clicking a 'x' icon on a tag pill removes it.  
* Component manages the list of current tags internally.  
* Component provides the current list of tag strings via a callback prop (onChange).  
* Duplicate tags (case-insensitive) are prevented or handled gracefully.  
* Matches the visual design from KC-CARD-UX-1-BLOCK.  
* (Optional Stage 1+) Basic autocomplete/suggestions based on existing tags could be added later.  
  Technical Approach / Implementation Notes:  
* Create src/components/tags/TagInput.tsx. Mark as 'use client'.  
* Use Chakra UI components: FormControl, FormLabel, Input, Box, Tag (or Badge), TagLabel, TagCloseButton, Wrap (for pill layout).  
* Use useState to manage the list of tag strings (tags: string\[\]) and the current input value (inputValue: string).  
* Handle onKeyDown on the Input: If Enter or Comma is pressed, trim the inputValue, check if it's non-empty and not already included (case-insensitive check), add it to the tags array, clear inputValue, and call props.onChange(\[...tags, newTag\]). Prevent default form submission if needed.  
* Handle onChange on the Input to update inputValue.  
* Render the tags array as Chakra Tag components within a Wrap. Each Tag should have a TagCloseButton with an onClick handler to remove that tag from the tags array and call props.onChange.  
* Define props: interface TagInputProps { value: string\[\]; onChange: (tags: string\[\]) \=\> void; placeholder?: string; }. Use value prop to initialize/control tags from parent.  
* Implement case-insensitive duplicate check before adding a tag.  
  API Contract (if applicable): N/A (UI Component)  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/components/tags/TagInput.tsx  
* Chakra UI components (Input, Tag, Wrap, etc.)  
* React useState, event handlers (onKeyDown, onChange, onClick)  
  Testing Considerations (Technical): Unit test component logic: adding tags (Enter/Comma), removing tags (close button), duplicate prevention, onChange callback firing with correct data.  
  Dependencies (Technical): KC-SETUP-3

Ticket ID: KC-CARD-FE-1-BLOCK (Generated)  
Title: Implement Block Editor Frontend Component  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1  
Team: FE  
Dependencies (Functional): KC-SETUP-3 (BlockNote installed), KC-CARD-UX-1-BLOCK (Design)  
UX/UI Design Link: \[Link to Figma/mockups for Block Editor\]  
Description (Functional): Create a reusable React component that wraps the BlockNote editor, configured for the basic text blocks and formatting options required in Stage 1\.  
Acceptance Criteria (Functional):

* Component renders a functional BlockNote editor instance.  
* Editor supports Paragraph, H1, H2, H3, Bullet List, Numbered List blocks.  
* Slash commands (/) are enabled for creating these blocks.  
* A floating toolbar appears on text selection, allowing Bold and Italic formatting.  
* The editor's content can be set via a prop (e.g., initialContent).  
* The editor's current content (as BlockNote JSON) is accessible via a callback prop (onChange).  
* Styling matches (or is customized to match) the design from KC-CARD-UX-1-BLOCK and Chakra UI theme.  
  Technical Approach / Implementation Notes:  
* Create src/components/editor/BlockEditor.tsx. Mark as 'use client'.  
* Import necessary components from @blocknote/react (BlockNoteView, useBlockNote) and @blocknote/core (BlockNoteEditor, PartialBlock).  
* Define props: interface BlockEditorProps { initialContent?: PartialBlock\[\]; onChange: (blocks: PartialBlock\[\]) \=\> void; editable?: boolean; }. Default editable to true.  
* Inside the component:  
  * Create the editor instance: const editor: BlockNoteEditor \= useBlockNote({ initialContent: props.initialContent, onEditorContentChange: (editor) \=\> { props.onChange(editor.topLevelBlocks); }, // Basic blocks are default, configure allowedBlocks if needed });  
  * Render the editor view: \<BlockNoteView editor={editor} editable={props.editable} theme="light" /\> (Choose theme or implement custom styling).  
* **Styling:** Import BlockNote CSS (@import "@blocknote/core/style.css";) globally or scope it. Customize BlockNote theme variables or override CSS classes to match Chakra UI / UX design. Refer to BlockNote theming documentation.  
* Ensure editor state updates correctly trigger the onChange prop.  
  API Contract (if applicable): N/A (UI Component)  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/components/editor/BlockEditor.tsx  
* @blocknote/react (BlockNoteView, useBlockNote)  
* @blocknote/core (BlockNoteEditor, PartialBlock)  
* CSS for styling/theming  
  Testing Considerations (Technical): Unit test component rendering. Test that onChange is called when editor content changes. Test initialContent prop populates the editor. Test editable prop disables editing. (E2E tests are better for testing actual editor interactions).  
  Dependencies (Technical): KC-SETUP-3, KC-CARD-UX-1-BLOCK

Ticket ID: KC-23-BLOCK  
Title: Create API endpoint to Create Card with JSON Content  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1, FR-CARD-2  
Team: BE  
Dependencies (Functional): KC-20.1-BLOCK (Card Schema), KC-20.2 (Tag Schema), KC-8.2 (Auth Check), KC-25.1 (Tag Handling Logic)  
UX/UI Design Link: N/A  
Description (Functional): Implement the backend logic to save a new card created using the block editor, including its title, structured content (JSON), associated tags, and optional folder assignment.  
Acceptance Criteria (Functional):

* Sending valid title, block content (JSON), and optional tags/folderId to the API (POST /api/cards) creates a new card record associated with the logged-in user.  
* The saved content field accurately reflects the JSON structure provided by the BlockNote editor.  
* Tags are correctly created (if new, case-insensitive) and associated with the new card using the logic from KC-25.1.  
* If folderId is provided, the card is associated with that folder (ownership check needed later in KC-ORG).  
* Requests fail with 401 if user is not authenticated.  
* Requests fail with 400 if title is missing, content is not valid JSON, or tag/folder data is malformed.  
* Returns the newly created card data (including generated ID and relations) on success (201).  
  Technical Approach / Implementation Notes:  
* Create app/api/cards/route.ts. Export async function POST(request: Request).  
* Import NextResponse, prisma, getCurrentUserId, getTagConnectionsForUpsert (from lib/tags), zod.  
* Define Zod schema for request body validation:  
  const CreateCardSchema \= z.object({  
    title: z.string().min(1, { message: "Title cannot be empty" }),  
    // Validate content is an array (basic BlockNote structure)  
    // More specific validation using BlockNote types might be complex here  
    content: z.array(z.any()).min(1, { message: "Content cannot be empty" }),  
    tags: z.array(z.string()).optional(),  
    folderId: z.string().cuid().optional().nullable(), // Allow null or valid CUID  
  });

* Inside POST:  
  * const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
  * const body \= await request.json();  
  * const validation \= CreateCardSchema.safeParse(body); if (\!validation.success) { /\* 400 \*/ }  
  * Prepare Prisma data object:  
    * title: validation.data.title  
    * content: validation.data.content // Prisma expects JSON serializable data  
    * userId: userId  
    * folderId: validation.data.folderId // Basic association for now  
    * tags: {} // Placeholder for tag connections  
  * If validation.data.tags exist and have items:  
    * const tagConnections \= await getTagConnectionsForUpsert(validation.data.tags);  
    * prismaData.tags \= { connectOrCreate: tagConnections };  
  * Use try/catch for Prisma create.  
  * const newCard \= await prisma.card.create({ data: prismaData, include: { tags: true, folder: true } }); // Include relations in response  
  * Return NextResponse.json(newCard, { status: 201 });  
  * Handle Prisma errors (e.g., foreign key constraint if folderId is invalid) and other errors (500).  
    API Contract (if applicable):  
* **Endpoint:** POST /api/cards  
* **Request Body:** { title: string, content: PartialBlock\[\], tags?: string\[\], folderId?: string | null } (Using BlockNote PartialBlock\[\] type ideally)  
* **Response Success (201):** Full Card object (Prisma type, includes id, content JSON, and populated tags, folder relations).  
* **Response Error (400):** { errors: ZodError } or { error: string }  
* **Response Error (401):** { error: 'Unauthorized' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): Creates Card record and potentially Tag records. Creates associations in \_CardToTag.  
  Key Functions/Modules Involved:  
* app/api/cards/route.ts  
* lib/sessionUtils.ts (getCurrentUserId)  
* lib/prisma.ts (Prisma Client)  
* lib/tags.ts (getTagConnectionsForUpsert)  
* zod  
  Testing Considerations (Technical): Unit test validation, tag connection logic, Prisma create call. Test API with valid/invalid BlockNote JSON, with/without tags, with/without folderId. Test auth requirement.  
  Dependencies (Technical): KC-20.1-BLOCK, KC-20.2, KC-8.2, KC-25.1

Ticket ID: KC-CARD-FE-2-BLOCK (Generated)  
Title: Implement Card Creation Page UI & Logic  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1, FR-CARD-2  
Team: FE  
Dependencies (Functional): KC-CARD-FE-1-BLOCK (Editor Comp), KC-CARD-FE-7-BLOCK (Tag Input Comp), KC-23-BLOCK (Create API), KC-AUTH-FE-4 (AuthGuard)  
UX/UI Design Link: \[Link to Figma/mockups for Card Create Page\]  
Description (Functional): Create the user interface for composing a new knowledge card, including fields for title, the block editor for content, tag input, and a save button.  
Acceptance Criteria (Functional):

* A "Create Card" page is accessible (e.g., at /cards/new) only to logged-in users.  
* Page includes an Input for the card Title.  
* Page includes the BlockEditor component (KC-CARD-FE-1-BLOCK).  
* Page includes the TagInput component (KC-CARD-FE-7-BLOCK).  
* A "Save Card" button triggers the creation process.  
* Form state (title, editor content, tags) is managed (e.g., using useState or react-hook-form).  
* Clicking "Save" calls the POST /api/cards endpoint with the current title, editor content (JSON), and tags.  
* Loading state is shown during the API call.  
* On success, a confirmation (e.g., Toast) is shown, and the user is redirected (e.g., to the new card's display page or a card list).  
* Validation errors (e.g., empty title) and API errors are displayed appropriately.  
  Technical Approach / Implementation Notes:  
* Create page route src/app/(protected)/cards/new/page.tsx. Mark as 'use client'. (Place in protected group).  
* Import useState, BlockEditor, TagInput, useRouter, useToast, Chakra components (Input, Button, FormControl, FormLabel, etc.).  
* Use useState to manage title: string, content: PartialBlock\[\], tags: string\[\], isLoading: boolean, apiError: string | null.  
* Implement handleSaveCard function:  
  * Perform basic client-side validation (e.g., title not empty).  
  * setIsLoading(true); setApiError(null);  
  * try { const response \= await fetch('/api/cards', { method: 'POST', ..., body: JSON.stringify({ title, content, tags }) }); ... } catch { ... } finally { setIsLoading(false); }  
  * On success (response.ok): Parse response to get new card ID (const newCard \= await response.json();), show toast, router.push(\\/cards/${newCard.id}\`);\`.  
  * On failure (\!response.ok): Parse error, set apiError.  
* Render the form:  
  * FormControl with Input for Title, bind to title state.  
  * BlockEditor component, passing onChange={setContent}.  
  * TagInput component, passing value={tags} and onChange={setTags}.  
  * "Save Card" Button, onClick={handleSaveCard}, isLoading={isLoading}.  
  * Display apiError if present.  
    API Contract (if applicable): Consumes POST /api/cards (KC-23-BLOCK).  
    Data Model Changes (if applicable): N/A  
    Key Functions/Modules Involved:  
* src/app/(protected)/cards/new/page.tsx  
* src/components/editor/BlockEditor.tsx  
* src/components/tags/TagInput.tsx  
* React useState, fetch  
* next/navigation (useRouter)  
* @chakra-ui/react (useToast, layout components)  
  Testing Considerations (Technical): E2E test creating a card with title, content, and tags. Unit test handleSaveCard logic (mocking fetch, router, toast). Test basic client-side validation.  
  Dependencies (Technical): KC-CARD-FE-1-BLOCK, KC-CARD-FE-7-BLOCK, KC-23-BLOCK, KC-AUTH-FE-4

Ticket ID: KC-CARD-BE-1-BLOCK (Generated)  
Title: Create API endpoint to fetch a single card  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1 (Implied for display/edit)  
Team: BE  
Dependencies (Functional): KC-20.1-BLOCK (Card Schema), KC-8.2 (Auth Check)  
UX/UI Design Link: N/A  
Description (Functional): Provide a backend endpoint to retrieve the data for a specific knowledge card, ensuring the requesting user owns the card.  
Acceptance Criteria (Functional):

* Sending a GET request to /api/cards/{cardId} returns the full card data (title, content JSON, tags, folder, timestamps) if the card exists and belongs to the logged-in user.  
* Returns 404 Not Found if the card ID doesn't exist or doesn't belong to the user (to avoid revealing existence).  
* Returns 401 Unauthorized if the user is not logged in.  
* Returns 400 Bad Request if the provided cardId is not a valid format (e.g., CUID).  
  Technical Approach / Implementation Notes:  
* Create dynamic route app/api/cards/\[cardId\]/route.ts. Export async function GET(request: Request, { params }: { params: { cardId: string } }).  
* Import NextResponse, prisma, getCurrentUserId.  
* Validate params.cardId format (e.g., using a regex or CUID library). Return 400 if invalid.  
* const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
* Use try/catch for Prisma query.  
* const card \= await prisma.card.findUnique({ where: { id: params.cardId, userId: userId }, include: { tags: true, folder: true } });  
  * **Crucially, include userId in the where clause to enforce ownership.**  
* if (\!card) { return NextResponse.json({ error: 'Card not found' }, { status: 404 }); }  
* return NextResponse.json(card);  
* Handle Prisma errors (500).  
  API Contract (if applicable):  
* **Endpoint:** GET /api/cards/{cardId}  
* **Request:** URL parameter cardId. Auth via session.  
* **Response Success (200):** Full Card object (including relations).  
* **Response Error (400):** { error: 'Invalid card ID format' }  
* **Response Error (401):** { error: 'Unauthorized' }  
* **Response Error (404):** { error: 'Card not found' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* app/api/cards/\[cardId\]/route.ts  
* lib/sessionUtils.ts (getCurrentUserId)  
* lib/prisma.ts (Prisma Client)  
  Testing Considerations (Technical): Test fetching owned card (success). Test fetching non-existent card (404). Test fetching card owned by another user (404). Test without authentication (401). Test with invalid ID format (400).  
  Dependencies (Technical): KC-20.1-BLOCK, KC-8.2

Ticket ID: KC-CARD-FE-3-BLOCK (Generated)  
Title: Implement Card Display Page UI  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1 (Implied for viewing)  
Team: FE  
Dependencies (Functional): KC-CARD-BE-1-BLOCK (Fetch API), KC-CARD-FE-1-BLOCK (Editor Comp for read-only), KC-AUTH-FE-4 (AuthGuard)  
UX/UI Design Link: \[Link to Figma/mockups for Card Display Page\]  
Description (Functional): Create the page to view a single knowledge card, displaying its title, tags, and rendering the block editor content in a read-only mode.  
Acceptance Criteria (Functional):

* A page is accessible at /cards/{cardId} only to the logged-in owner of the card.  
* The page fetches card data from GET /api/cards/{cardId} on load.  
* Displays the card Title (e.g., as Heading).  
* Displays associated Tags (e.g., using Chakra Tag components).  
* Renders the card content (JSON) using the BlockEditor component configured in editable={false} mode.  
* Handles loading state while fetching data.  
* Handles errors (e.g., card not found, unauthorized) gracefully.  
* Includes buttons/links for Edit and Delete actions (functionality implemented in later tickets).  
  Technical Approach / Implementation Notes:  
* Create dynamic page route src/app/(protected)/cards/\[cardId\]/page.tsx. Mark as 'use client'.  
* Import useEffect, useState, useParams, BlockEditor, Chakra components, Link from next/link.  
* Get cardId from useParams().  
* Use useState for cardData: Card | null, isLoading: boolean, error: string | null.  
* Use useEffect to fetch data when cardId changes:  
  * setIsLoading(true); setError(null);  
  * fetch(\\/api/cards/${cardId}\`)\`  
  * On success (response.ok): setCardData(await response.json());  
  * On failure: Handle 401/403 (redirect?), 404 (setError('Card not found')), 500 (setError('Failed to load card')).  
  * setIsLoading(false);  
* Render logic:  
  * If isLoading, show Spinner.  
  * If error, show error message.  
  * If cardData:  
    * Display cardData.title (e.g., Heading).  
    * Display cardData.tags (map to Chakra Tags).  
    * Render \<BlockEditor initialContent={cardData.content} onChange={() \=\> {}} editable={false} /\>. (Need to ensure content is correct type PartialBlock\[\]).  
    * Add Edit button/link (\<Link href={\\/cards/${cardId}/edit\`}\>\`).  
    * Add Delete button (logic in KC-CARD-FE-5-BLOCK).  
      API Contract (if applicable): Consumes GET /api/cards/{cardId} (KC-CARD-BE-1-BLOCK).  
      Data Model Changes (if applicable): N/A  
      Key Functions/Modules Involved:  
* src/app/(protected)/cards/\[cardId\]/page.tsx  
* src/components/editor/BlockEditor.tsx  
* React useState, useEffect, fetch  
* next/navigation (useParams)  
* next/link (Link)  
* Chakra UI components  
  Testing Considerations (Technical): E2E test viewing an owned card. Test loading state. Test error handling (not found, unauthorized). Unit test data fetching logic (mock fetch). Test rendering of title, tags, and read-only editor.  
  Dependencies (Technical): KC-CARD-BE-1-BLOCK, KC-CARD-FE-1-BLOCK, KC-AUTH-FE-4

Ticket ID: KC-CARD-BE-2-BLOCK (Generated)  
Title: Create API endpoint to update a card  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1 (Implied for editing)  
Team: BE  
Dependencies (Functional): KC-CARD-BE-1-BLOCK (Ownership check pattern), KC-25.1 (Tag Handling), KC-20.1-BLOCK (Schema)  
UX/UI Design Link: N/A  
Description (Functional): Implement the backend logic to update an existing knowledge card's title, content, tags, or folder association, ensuring user ownership.  
Acceptance Criteria (Functional):

* Sending a PUT request to /api/cards/{cardId} with valid data updates the specified card if it exists and belongs to the logged-in user.  
* Allows updating title, content (JSON), tags (replacing existing tags), and folderId individually or together.  
* Tag updates use the find-or-create logic (KC-25.1) and replace the card's existing tag associations.  
* Returns the updated card data on success.  
* Returns 404 if card not found or not owned by the user.  
* Returns 401 if user not logged in.  
* Returns 400 if input data is invalid (e.g., empty title, invalid JSON, bad ID format).  
  Technical Approach / Implementation Notes:  
* In app/api/cards/\[cardId\]/route.ts, export async function PUT(request: Request, { params }: { params: { cardId: string } }).  
* Import NextResponse, prisma, getCurrentUserId, getTagConnectionsForUpsert, zod.  
* Validate params.cardId format (400 if invalid).  
* const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
* Define Zod schema for update (make fields optional): UpdateCardSchema \= CreateCardSchema.partial(); (Reuse parts of create schema).  
* const body \= await request.json();  
* const validation \= UpdateCardSchema.safeParse(body); if (\!validation.success) { /\* 400 \*/ }  
* Use try/catch.  
* **Check ownership first:** const existingCard \= await prisma.card.findUnique({ where: { id: params.cardId, userId: userId } }); if (\!existingCard) { /\* 404 \*/ }  
* Prepare data for update: Include validated fields (title, content, folderId) if present in validation.data.  
* Handle tags:  
  * If validation.data.tags is present (even if empty array):  
    * const tagConnections \= await getTagConnectionsForUpsert(validation.data.tags);  
    * Set prismaUpdateData.tags \= { set: \[\], connectOrCreate: tagConnections }; (set: \[\] disconnects all existing tags before connecting new/updated ones).  
* const updatedCard \= await prisma.card.update({ where: { id: params.cardId /\* No userId needed here, checked above \*/ }, data: prismaUpdateData, include: { tags: true, folder: true } });  
* Return NextResponse.json(updatedCard);  
* Handle Prisma errors (500).  
  API Contract (if applicable):  
* **Endpoint:** PUT /api/cards/{cardId}  
* **Request Body:** { title?: string, content?: PartialBlock\[\], tags?: string\[\], folderId?: string | null } (Fields are optional)  
* **Response Success (200):** Full updated Card object.  
* **Response Error (400):** { errors: ZodError } or { error: string }  
* **Response Error (401):** { error: 'Unauthorized' }  
* **Response Error (404):** { error: 'Card not found' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): Updates Card record. Modifies associations in \_CardToTag. Potentially creates Tag records.  
  Key Functions/Modules Involved:  
* app/api/cards/\[cardId\]/route.ts  
* lib/sessionUtils.ts, lib/prisma.ts, lib/tags.ts, zod  
  Testing Considerations (Technical): Test updating title, content, tags (add/remove/change), folderId individually and together. Test ownership check (404). Test auth (401). Test validation (400). Test tag replacement logic.  
  Dependencies (Technical): KC-CARD-BE-1-BLOCK, KC-25.1, KC-20.1-BLOCK

Ticket ID: KC-CARD-FE-4-BLOCK (Generated)  
Title: Implement Card Editing Page UI & Logic  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1 (Implied for editing)  
Team: FE  
Dependencies (Functional): KC-CARD-FE-3-BLOCK (Uses similar structure), KC-CARD-BE-2-BLOCK (Update API), KC-CARD-FE-1-BLOCK (Editor Comp), KC-CARD-FE-7-BLOCK (Tag Input)  
UX/UI Design Link: \[Link to Figma/mockups for Card Edit Page\]  
Description (Functional): Create the user interface for editing an existing knowledge card, pre-populating the form with current data and allowing updates.  
Acceptance Criteria (Functional):

* An edit page is accessible (e.g., at /cards/{cardId}/edit) only to the card owner.  
* Page fetches the current card data from GET /api/cards/{cardId} on load.  
* Form fields (Title Input, BlockEditor, TagInput) are pre-populated with the fetched card data.  
* An "Update Card" button triggers the update process.  
* Clicking "Update" calls the PUT /api/cards/{cardId} endpoint with changed data.  
* Loading state is shown during fetch and update calls.  
* On success, a confirmation is shown, and the user is redirected (e.g., back to the card display page).  
* Errors (fetch errors, validation errors, update errors) are handled gracefully.  
  Technical Approach / Implementation Notes:  
* Create dynamic page route src/app/(protected)/cards/\[cardId\]/edit/page.tsx. Mark as 'use client'.  
* Structure similar to Create Page (KC-CARD-FE-2-BLOCK) and Display Page (KC-CARD-FE-3-BLOCK).  
* Fetch initial card data using useEffect and fetch(\\/api/cards/${cardId}\`). Store in useState\`. Handle loading/error states.  
* Use useState or react-hook-form (useForm with defaultValues populated from fetched data) to manage form state (title, content, tags).  
* If using useState, update state variables when fetched data arrives. If using react-hook-form, use reset(fetchedData) in useEffect.  
* Implement handleUpdateCard function:  
  * Perform validation.  
  * setIsLoading(true);  
  * fetch(\\/api/cards/${cardId}\`, { method: 'PUT', ..., body: JSON.stringify({ title, content, tags }) });\`  
  * Handle success (toast, router.push(\\/cards/${cardId}\`)) and errors (setApiError\`).  
  * setIsLoading(false);  
* Render the form similar to Create Page, but pre-populate fields and use "Update Card" button text. Pass fetched initialContent to BlockEditor. Pass fetched tags to TagInput.  
  API Contract (if applicable): Consumes GET /api/cards/{cardId} (KC-CARD-BE-1-BLOCK) and PUT /api/cards/{cardId} (KC-CARD-BE-2-BLOCK).  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/app/(protected)/cards/\[cardId\]/edit/page.tsx  
* src/components/editor/BlockEditor.tsx  
* src/components/tags/TagInput.tsx  
* React useState, useEffect, fetch  
* next/navigation (useParams, useRouter)  
* @chakra-ui/react (useToast, layout components)  
* (Optional) react-hook-form  
  Testing Considerations (Technical): E2E test editing a card's title, content, and tags. Test loading/error states during fetch and update. Unit test handleUpdateCard logic. Test form pre-population.  
  Dependencies (Technical): KC-CARD-FE-3-BLOCK, KC-CARD-BE-2-BLOCK, KC-CARD-FE-1-BLOCK, KC-CARD-FE-7-BLOCK

Ticket ID: KC-CARD-BE-3-BLOCK (Generated)  
Title: Create API endpoint to delete a card  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1 (Implied for deleting)  
Team: BE  
Dependencies (Functional): KC-CARD-BE-1-BLOCK (Ownership check pattern)  
UX/UI Design Link: N/A  
Description (Functional): Implement the backend logic to permanently delete a knowledge card, ensuring user ownership.  
Acceptance Criteria (Functional):

* Sending a DELETE request to /api/cards/{cardId} permanently deletes the card if it exists and belongs to the logged-in user.  
* Returns a success response (e.g., 200 OK or 204 No Content) on successful deletion.  
* Returns 404 if card not found or not owned by the user.  
* Returns 401 if user not logged in.  
* Returns 400 if cardId format is invalid.  
  Technical Approach / Implementation Notes:  
* In app/api/cards/\[cardId\]/route.ts, export async function DELETE(request: Request, { params }: { params: { cardId: string } }).  
* Import NextResponse, prisma, getCurrentUserId.  
* Validate params.cardId format (400 if invalid).  
* const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
* Use try/catch.  
* **Check ownership first:** const existingCard \= await prisma.card.findUnique({ where: { id: params.cardId, userId: userId }, select: { id: true } }); if (\!existingCard) { /\* 404 \*/ } (Select only id for efficiency).  
* await prisma.card.delete({ where: { id: params.cardId /\* No userId needed here, checked above \*/ } });  
* Return NextResponse.json({ message: 'Card deleted successfully' }, { status: 200 }); (or NextResponse.next({ status: 204 })).  
* Handle Prisma errors (e.g., record not found if deleted between check and delete \- handle gracefully) and other errors (500).  
  API Contract (if applicable):  
* **Endpoint:** DELETE /api/cards/{cardId}  
* **Request:** URL parameter cardId. Auth via session.  
* **Response Success (200):** { message: 'Card deleted successfully' }  
* **Response Success (204):** No body content.  
* **Response Error (400):** { error: 'Invalid card ID format' }  
* **Response Error (401):** { error: 'Unauthorized' }  
* **Response Error (404):** { error: 'Card not found' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): Deletes Card record. Prisma handles cascading deletes or relation cleanup based on schema (onDelete).  
  Key Functions/Modules Involved:  
* app/api/cards/\[cardId\]/route.ts  
* lib/sessionUtils.ts, lib/prisma.ts  
  Testing Considerations (Technical): Test deleting owned card (success). Test deleting non-existent card (404). Test deleting card owned by another user (404). Test without authentication (401). Test with invalid ID (400). Verify card is actually removed from DB.  
  Dependencies (Technical): KC-CARD-BE-1-BLOCK

Ticket ID: KC-CARD-FE-5-BLOCK (Generated)  
Title: Implement Card Deletion UI Logic  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1 (Implied for deleting)  
Team: FE  
Dependencies (Functional): KC-CARD-FE-3-BLOCK (Button location), KC-CARD-BE-3-BLOCK (Delete API)  
UX/UI Design Link: \[Link to Figma/mockups for Delete Confirmation\]  
Description (Functional): Add functionality to the card display page (or card list items) allowing users to initiate card deletion, typically involving a confirmation step.  
Acceptance Criteria (Functional):

* A "Delete" button is present on the card display page (KC-CARD-FE-3-BLOCK).  
* Clicking the "Delete" button prompts the user for confirmation (e.g., using a Chakra UI AlertDialog).  
* Confirming deletion calls the DELETE /api/cards/{cardId} endpoint.  
* Loading state is shown during the API call.  
* On successful deletion, a confirmation message (e.g., Toast) is shown, and the user is redirected (e.g., to the card list/dashboard).  
* Errors during deletion are handled gracefully.  
  Technical Approach / Implementation Notes:  
* Modify the component where the delete button resides (e.g., src/app/(protected)/cards/\[cardId\]/page.tsx).  
* Import useDisclosure, AlertDialog, AlertDialogBody, AlertDialogFooter, AlertDialogHeader, AlertDialogContent, AlertDialogOverlay, Button, useToast, useRouter.  
* Use useDisclosure for managing the AlertDialog state (isOpen, onOpen, onClose).  
* Add a "Delete" Button that calls onOpen.  
* Render the AlertDialog:  
  * Include appropriate header ("Delete Card?") and body ("Are you sure? You can't undo this action.").  
  * Footer contains a "Cancel" button (onClick={onClose}) and a "Delete" button (onClick={handleDeleteConfirm}, colorScheme='red', isLoading={isDeleting}).  
* Use useState for isDeleting state.  
* Implement async function handleDeleteConfirm():  
  * setIsDeleting(true);  
  * try { const response \= await fetch(\\/api/cards/${cardId}\`, { method: 'DELETE' }); ... } catch { ... } finally { setIsDeleting(false); onClose(); }\`  
  * On success (response.ok): Show toast, router.push('/dashboard'); (or card list page).  
  * On failure: Show error toast.  
    API Contract (if applicable): Consumes DELETE /api/cards/{cardId} (KC-CARD-BE-3-BLOCK).  
    Data Model Changes (if applicable): N/A  
    Key Functions/Modules Involved:  
* Card display page component (e.g., src/app/(protected)/cards/\[cardId\]/page.tsx)  
* Chakra UI AlertDialog, useDisclosure, Button, useToast  
* React useState, fetch  
* next/navigation (useRouter)  
  Testing Considerations (Technical): E2E test the delete flow including confirmation dialog. Unit test handleDeleteConfirm logic (mocking fetch, router, toast). Test cancel action on dialog.  
  Dependencies (Technical): KC-CARD-FE-3-BLOCK, KC-CARD-BE-3-BLOCK

Ticket ID: KC-CARD-BE-4-BLOCK (Generated)  
Title: Create API endpoint to list user's cards  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1 (Implied for listing/dashboard)  
Team: BE  
Dependencies (Functional): KC-20.1-BLOCK (Card Schema), KC-8.2 (Auth Check)  
UX/UI Design Link: N/A  
Description (Functional): Provide a basic backend endpoint to retrieve a list of cards belonging to the currently logged-in user. Stage 1: Simple list, no pagination/sorting yet.  
Acceptance Criteria (Functional):

* Sending a GET request to /api/cards returns a list of cards owned by the logged-in user.  
* Each item in the list includes essential fields for display (e.g., id, title, updatedAt, maybe first few tags).  
* Returns an empty list if the user has no cards.  
* Returns 401 Unauthorized if the user is not logged in.  
  Technical Approach / Implementation Notes:  
* In app/api/cards/route.ts, export async function GET(request: Request). (This file now handles POST and GET for the collection).  
* Import NextResponse, prisma, getCurrentUserId.  
* const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
* Use try/catch.  
* const cards \= await prisma.card.findMany({ where: { userId: userId }, select: { id: true, title: true, updatedAt: true, tags: { select: { name: true }, take: 3 } // Select limited fields }, orderBy: { updatedAt: 'desc' } // Simple default sort });  
* Return NextResponse.json(cards);  
* Handle Prisma errors (500).  
  API Contract (if applicable):  
* **Endpoint:** GET /api/cards  
* **Request:** Auth via session. (Query params for pagination/sort/filter in later stages).  
* **Response Success (200):** Array\<{ id: string, title: string, updatedAt: Date, tags: Array\<{ name: string }\> }\>  
* **Response Error (401):** { error: 'Unauthorized' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* app/api/cards/route.ts  
* lib/sessionUtils.ts, lib/prisma.ts  
  Testing Considerations (Technical): Test listing cards for user with cards, user with no cards. Test auth requirement (401). Verify only necessary fields are returned. Test default sorting.  
  Dependencies (Technical): KC-20.1-BLOCK, KC-8.2

Ticket ID: KC-CARD-FE-6-BLOCK (Generated)  
Title: Implement Basic Card List UI  
Epic: KC-CARD-CREATE  
PRD Requirement(s): FR-CARD-1 (Implied for listing/dashboard)  
Team: FE  
Dependencies (Functional): KC-CARD-BE-4-BLOCK (List API), KC-AUTH-FE-4 (AuthGuard)  
UX/UI Design Link: \[Link to Figma/mockups for Card List/Dashboard\]  
Description (Functional): Display a simple list of the user's knowledge cards, typically on a main dashboard or dedicated "My Cards" page.  
Acceptance Criteria (Functional):

* A page (e.g., /dashboard) displays a list of cards fetched from GET /api/cards.  
* Each card item shows at least the title and last updated time.  
* Each card item is clickable, linking to the card's display page (/cards/{cardId}).  
* Handles loading state while fetching the list.  
* Displays a message if the user has no cards yet.  
* Page is accessible only to logged-in users.  
  Technical Approach / Implementation Notes:  
* Create/Modify page route (e.g., src/app/(protected)/dashboard/page.tsx). Mark as 'use client'.  
* Import useEffect, useState, Chakra components (Box, VStack, Heading, Text, Spinner, Link as ChakraLink), Link from next/link.  
* Use useState for cards: CardListItem\[\], isLoading: boolean, error: string | null. (Define CardListItem type based on API response).  
* Use useEffect to fetch data from /api/cards. Handle loading/error states.  
* Render logic:  
  * If isLoading, show Spinner.  
  * If error, show error message.  
  * If \!isLoading && cards.length \=== 0, show "No cards yet." message and link to create page.  
  * If cards.length \> 0, map over cards array:  
    * For each card, render a container (Box, ListItem).  
    * Inside, use Link (from next/link) wrapping the content, pointing to /cards/${card.id}.  
    * Display card.title (e.g., Heading size='sm').  
    * Display card.updatedAt (format nicely).  
    * (Optional) Display first few card.tags.  
* Include a prominent "Create New Card" button/link on the page.  
  API Contract (if applicable): Consumes GET /api/cards (KC-CARD-BE-4-BLOCK).  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/app/(protected)/dashboard/page.tsx (or similar list page)  
* React useState, useEffect, fetch  
* next/link (Link)  
* Chakra UI components  
  Testing Considerations (Technical): E2E test viewing the dashboard with cards and without cards. Test clicking a card links to the correct display page. Unit test data fetching and rendering logic (mock fetch).  
  Dependencies (Technical): KC-CARD-BE-4-BLOCK, KC-AUTH-FE-4

Ticket ID: KC-CARD-TEST-BE-1-BLOCK
Title: Write Unit/Integration Tests for Card API Logic (Block Editor)
Epic: KC-CARD-CREATE
PRD Requirement(s): NFR-MAINT-1
Team: BE/QA
Dependencies (Functional): Card CRUD APIs (KC-23-BLOCK, KC-CARD-BE-1-BLOCK, KC-CARD-BE-2-BLOCK, KC-CARD-BE-3-BLOCK), KC-TEST-BE-1
UX/UI Design Link: N/A
Description (Functional): Create automated unit and integration tests for the backend API endpoints related to card CRUD operations, including JSON content handling and tag management.
Acceptance Criteria (Functional):
* Tests verify successful card creation (POST /api/cards) with valid title, content (JSON), and tags (including case-insensitive find-or-create logic).
* Tests verify successful retrieval (GET /api/cards/{cardId}) for owned cards and 404 for non-owned/non-existent cards.
* Tests verify successful card update (PUT /api/cards/{cardId}) for title, content, tags (tag replacement), and folderId, including ownership checks.
* Tests verify successful card deletion (DELETE /api/cards/{cardId}) including ownership checks.
* Tests cover validation errors (e.g., missing title, invalid content structure), auth errors (401), ownership errors (404), and DB errors (500) for all endpoints.
* Tests specifically validate the `getTagConnectionsForUpsert` logic (KC-25.1) via the create/update endpoints.
Technical Approach / Implementation Notes:
* Use Jest/Vitest and Supertest.
* Interact with a test database, seeding necessary user, tag, folder data.
* Mock `getCurrentUserId` (KC-8.2).
* Unit test `getTagConnectionsForUpsert` separately (as per KC-25.1) and integration test its use via APIs.
* Test cases for each endpoint: Success (various inputs), validation failures, auth failures, ownership failures, tag handling scenarios (new, existing, mixed case, replacement), DB errors.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `/app/api/cards/route.ts`, `/app/api/cards/[cardId]/route.ts`, `lib/tags.ts`, Test framework, Test DB utilities.
Testing Considerations (Technical): Thoroughly test tag connection logic. Verify ownership checks are present and effective. Test handling of valid and potentially invalid BlockNote JSON structures.
Dependencies (Technical): All Card CRUD API tickets, KC-TEST-BE-1, KC-25.1

Ticket ID: KC-CARD-TEST-FE-1-BLOCK
Title: Write Unit/Integration Tests for Card CRUD UI (Block Editor)
Epic: KC-CARD-CREATE
PRD Requirement(s): NFR-MAINT-1
Team: FE/QA
Dependencies (Functional): Card CRUD Pages/Components (KC-CARD-FE-1-BLOCK to 5-BLOCK, 7-BLOCK), KC-TEST-FE-1
UX/UI Design Link: N/A
Description (Functional): Create automated unit and integration tests for the frontend components and pages involved in card creation, viewing, editing, and deletion, including the Block Editor and Tag Input components.
Acceptance Criteria (Functional):
* Unit tests verify rendering and basic interaction logic of `BlockEditor`, `TagInput` components.
* Integration tests verify the Create Card page: form rendering, input handling, API call on submit, handling success (redirect) and error responses.
* Integration tests verify the View Card page: fetching data, rendering title/tags/read-only content, presence of Edit/Delete buttons.
* Integration tests verify the Edit Card page: fetching initial data, pre-populating form, API call on update, handling success (redirect) and errors.
* Integration tests verify the Delete Card confirmation dialog logic and API call.
* Tests cover loading and error states for API interactions.
Technical Approach / Implementation Notes:
* Use Jest/Vitest and React Testing Library.
* Mock `fetch` or data fetching hooks (SWR) to simulate API responses for CRUD operations.
* Mock `useRouter`, `useToast`, `useParams`.
* Mock `BlockEditor` and `TagInput` for page-level tests if needed, or test their integration directly.
* Simulate user interactions (typing, clicking, form submission).
* Assert component rendering, API calls, state changes, toasts, and router actions.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: Card CRUD pages (`/cards/new`, `/cards/[cardId]`, `/cards/[cardId]/edit`), `BlockEditor.tsx`, `TagInput.tsx`, Mocked hooks/fetch.
Testing Considerations (Technical): Focus on testing the flow of data between components and API mocks. Test handling of BlockNote content structure in create/edit/view flows. Verify confirmation dialog logic for deletion.
Dependencies (Technical): All Card CRUD FE tickets, KC-TEST-FE-1