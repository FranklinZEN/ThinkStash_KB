## **JIRA Epic: KC-ORG \- Folder Management (Stage 1\)**

**Rationale:** Provide basic hierarchical organization for cards using local data storage.

Ticket ID: KC-ORG-UX-1  
Title: Design Folder Management UI & Interactions  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-1, FR-ORG-2, FR-ORG-3  
Team: UX  
Dependencies (Functional): KC-SETUP-3 (Chakra UI)  
UX/UI Design Link: \[Link to Figma/mockups\]  
Description (Functional): Design the user interface for creating, viewing, renaming, deleting, and organizing folders, typically within a sidebar. Design how users move cards into folders.  
Acceptance Criteria (Functional):

* Mockups show a hierarchical folder tree structure (e.g., in a sidebar).  
* Designs detail interactions for creating a new folder (e.g., right-click menu, button).  
* Designs detail interactions for renaming a folder (e.g., right-click menu, inline edit).  
* Designs detail interactions for deleting a folder (e.g., right-click menu, confirmation dialog).  
* Designs specify how folder selection filters the main card view.  
* Designs detail the interaction for moving a card into a folder (e.g., drag-and-drop card onto folder, "Move to" button/menu on card).  
* Error states (e.g., trying to delete non-empty folder) and confirmation dialogs are designed.  
* Designs are responsive and include detailed specs.  
  Technical Approach / Implementation Notes:  
* Specify visual representation of nested folders (indentation, icons like open/closed arrows).  
* Define context menu options (Create, Rename, Delete).  
* Detail modal/dialog appearance for Create, Rename, Delete confirmation using Chakra UI components.  
* Specify drag-and-drop interaction visuals (ghost element, drop target highlighting).  
* Ensure accessibility considerations (keyboard navigation for tree, context menus, drag-and-drop alternatives).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved: N/A (Design artifact)  
  Testing Considerations (Technical): Usability testing on prototypes. Accessibility review.  
  Dependencies (Technical): KC-SETUP-3

Ticket ID: KC-40  
Title: Define Folder Schema in Prisma  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-1  
Team: BE  
Dependencies (Functional): KC-SETUP-2 (Prisma), KC-3.1 (User model), KC-20.1-BLOCK (Card model)  
UX/UI Design Link: N/A  
Description (Functional): Define the database structure for folders, allowing them to be nested hierarchically and associated with a user and cards.  
Acceptance Criteria (Functional):

* The database Folder table can store a name, associate with a User, and reference a parent folder for nesting.  
* The Card table can reference a folder.  
* Timestamps for folder creation/update are recorded.  
  Technical Approach / Implementation Notes:  
* Edit prisma/schema.prisma. Define model Folder:  
  model Folder {  
    id        String   @id @default(cuid())  
    name      String  
    createdAt DateTime @default(now())  
    updatedAt DateTime @updatedAt

    // Relation to User  
    userId    String  
    user      User     @relation(fields: \[userId\], references: \[id\], onDelete: Cascade) // Delete folders if user is deleted

    // Self-relation for nesting  
    parentId  String?  
    parent    Folder?  @relation("FolderHierarchy", fields: \[parentId\], references: \[id\], onDelete: Cascade) // If parent deleted, delete child  
    children  Folder\[\] @relation("FolderHierarchy")

    // Relation to Cards  
    cards     Card\[\]   // Cards within this folder

    @@unique(\[userId, parentId, name\]) // Prevent duplicate names within the same parent folder for a user  
    @@index(\[userId\])  
    @@index(\[parentId\])  
  }

* Ensure the corresponding relation field exists in model Card (added in KC-20.1-BLOCK):  
  // Inside model Card  
  folderId  String?  
  folder    Folder?  @relation(fields: \[folderId\], references: \[id\], onDelete: SetNull) // If folder deleted, set card's folderId to null

* Run npx prisma migrate dev \--name add-folder-model.  
* Run npx prisma generate.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): Adds Folder table with self-relation. Adds folderId/folder relation to Card. Adds unique constraint and indexes.  
  Key Functions/Modules Involved:  
* prisma/schema.prisma  
* prisma/migrations/...  
  Testing Considerations (Technical): Verify migration applies. Test unique constraint (name uniqueness within parent/user). Test onDelete behaviors (Cascade for user/parent, SetNull for card).  
  Dependencies (Technical): KC-SETUP-2, KC-3.1, KC-20.1-BLOCK

Ticket ID: KC-ORG-BE-1 (Generated)  
Title: Create API endpoint to List Folders (Tree Structure)  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-1 (Implied for display)  
Team: BE  
Dependencies (Functional): KC-40 (Folder Schema), KC-8.2 (Auth Check)  
UX/UI Design Link: N/A  
Description (Functional): Provide a backend endpoint to retrieve the user's folder hierarchy, structured appropriately for frontend tree rendering.  
Acceptance Criteria (Functional):

* Sending a GET request to /api/folders returns a list of the user's folders.  
* The response data is structured or easily transformable into a nested tree structure (e.g., a flat list containing id, name, parentId, or a recursively nested structure).  
* Returns 401 Unauthorized if the user is not logged in.  
  Technical Approach / Implementation Notes:  
* Create app/api/folders/route.ts. Export async function GET(request: Request).  
* Import NextResponse, prisma, getCurrentUserId.  
* const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
* Use try/catch.  
* Fetch all folders for the user:  
  const folders \= await prisma.folder.findMany({  
    where: { userId: userId },  
    select: { id: true, name: true, parentId: true, updatedAt: true }, // Select necessary fields  
    orderBy: { name: 'asc' } // Or createdAt  
  });

* **Decision:** Return flat list or build tree server-side?  
  * **Option A (Flat List \- Simpler):** Return the flat folders array directly. The frontend will be responsible for building the tree structure from the parentId references.  
  * **Option B (Nested Tree):** Implement a recursive function server-side to build the nested structure before sending the response. This can be more complex but might simplify frontend logic.  
  * **Recommendation for Stage 1:** Option A (Flat List) is generally simpler to implement initially.  
* Return NextResponse.json(folders); (if Option A).  
* Handle Prisma errors (500).  
  API Contract (if applicable):  
* **Endpoint:** GET /api/folders  
* **Request:** Auth via session.  
* **Response Success (200 \- Option A):** Array\<{ id: string, name: string, parentId: string | null, updatedAt: Date }\>  
* **Response Success (200 \- Option B):** Array\<{ id: string, name: string, children: Array\<...\> }\> (Nested structure)  
* **Response Error (401):** { error: 'Unauthorized' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* app/api/folders/route.ts  
* lib/sessionUtils.ts, lib/prisma.ts  
* (If Option B) Tree building utility function.  
  Testing Considerations (Technical): Test listing folders for user with folders (nested and root), user with no folders. Test auth requirement (401). Verify response format (flat or nested).  
  Dependencies (Technical): KC-40, KC-8.2

Ticket ID: KC-42.1  
Title: Create API endpoint to Create Folder  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-2  
Team: BE  
Dependencies (Functional): KC-40 (Folder Schema), KC-8.2 (Auth Check)  
UX/UI Design Link: N/A  
Description (Functional): Implement the backend logic to create a new folder, potentially nested under an existing parent folder.  
Acceptance Criteria (Functional):

* Sending a POST request to /api/folders with a valid name and optional parentId creates a new folder associated with the logged-in user.  
* If parentId is provided, it must correspond to an existing folder owned by the user.  
* Prevents creating folders with duplicate names within the same parent level for the user (utilizing the schema's unique constraint).  
* Returns the newly created folder data on success (201).  
* Returns 401 if user not logged in.  
* Returns 400 if name is missing/invalid, or if parentId is provided but invalid/not owned.  
* Returns 409 Conflict if a folder with the same name already exists at that level.  
  Technical Approach / Implementation Notes:  
* In app/api/folders/route.ts, export async function POST(request: Request).  
* Import NextResponse, prisma, getCurrentUserId, zod.  
* Define Zod schema: const CreateFolderSchema \= z.object({ name: z.string().min(1), parentId: z.string().cuid().optional().nullable() });.  
* const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
* const body \= await request.json();  
* const validation \= CreateFolderSchema.safeParse(body); if (\!validation.success) { /\* 400 \*/ }  
* Use try/catch.  
* **Validate parentId if provided:**  
  * If validation.data.parentId:  
    * const parentFolder \= await prisma.folder.findUnique({ where: { id: validation.data.parentId, userId: userId } });  
    * if (\!parentFolder) { return NextResponse.json({ error: 'Parent folder not found or not owned' }, { status: 400 }); }  
* Create folder:  
  const newFolder \= await prisma.folder.create({  
    data: {  
      name: validation.data.name,  
      userId: userId,  
      parentId: validation.data.parentId,  
    }  
  });

* Return NextResponse.json(newFolder, { status: 201 });  
* In catch block, handle Prisma errors:  
  * If error code indicates unique constraint violation (e.g., P2002 for userId\_parentId\_name\_key), return NextResponse.json({ error: 'Folder name already exists at this level' }, { status: 409 });.  
  * Handle other errors (500).  
    API Contract (if applicable):  
* **Endpoint:** POST /api/folders  
* **Request Body:** { name: string, parentId?: string | null }  
* **Response Success (201):** Full Folder object.  
* **Response Error (400):** { errors: ZodError } or { error: string }  
* **Response Error (401):** { error: 'Unauthorized' }  
* **Response Error (409):** { error: 'Folder name already exists at this level' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): Creates Folder record.  
  Key Functions/Modules Involved:  
* app/api/folders/route.ts  
* lib/sessionUtils.ts, lib/prisma.ts, zod  
  Testing Considerations (Technical): Test creating root folder, nested folder. Test validation (name, parentId). Test ownership check for parentId. Test unique name constraint (409). Test auth (401).  
  Dependencies (Technical): KC-40, KC-8.2

Ticket ID: KC-42.2  
Title: Create API endpoint to Update Folder (Rename)  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-2  
Team: BE  
Dependencies (Functional): KC-40 (Folder Schema), KC-8.2 (Auth Check)  
UX/UI Design Link: N/A  
Description (Functional): Implement the backend logic to rename an existing folder, ensuring user ownership and handling name uniqueness constraints.  
Acceptance Criteria (Functional):

* Sending a PUT request to /api/folders/{folderId} with a valid new name updates the folder's name if it exists and belongs to the user.  
* Prevents renaming to a name that already exists within the same parent folder for the user.  
* Returns the updated folder data on success.  
* Returns 404 if folder not found or not owned.  
* Returns 401 if user not logged in.  
* Returns 400 if the new name is invalid (e.g., empty).  
* Returns 409 Conflict if the new name already exists at that level.  
  Technical Approach / Implementation Notes:  
* Create app/api/folders/\[folderId\]/route.ts. Export async function PUT(request: Request, { params }: { params: { folderId: string } }).  
* Import NextResponse, prisma, getCurrentUserId, zod.  
* Validate params.folderId format (400 if invalid).  
* Define Zod schema: const UpdateFolderSchema \= z.object({ name: z.string().min(1) });.  
* const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
* const body \= await request.json();  
* const validation \= UpdateFolderSchema.safeParse(body); if (\!validation.success) { /\* 400 \*/ }  
* Use try/catch.  
* **Check ownership first:** const existingFolder \= await prisma.folder.findUnique({ where: { id: params.folderId, userId: userId } }); if (\!existingFolder) { /\* 404 \*/ }  
* Update folder:  
  const updatedFolder \= await prisma.folder.update({  
    where: { id: params.folderId /\* Ownership checked above \*/ },  
    data: { name: validation.data.name }  
  });

* Return NextResponse.json(updatedFolder);  
* In catch block, handle Prisma errors:  
  * If error code P2002 (unique constraint violation), return NextResponse.json({ error: 'Folder name already exists at this level' }, { status: 409 });.  
  * Handle other errors (500).  
    API Contract (if applicable):  
* **Endpoint:** PUT /api/folders/{folderId}  
* **Request Body:** { name: string }  
* **Response Success (200):** Full updated Folder object.  
* **Response Error (400):** { errors: ZodError } or { error: string }  
* **Response Error (401):** { error: 'Unauthorized' }  
* **Response Error (404):** { error: 'Folder not found' }  
* **Response Error (409):** { error: 'Folder name already exists at this level' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): Updates Folder.name.  
  Key Functions/Modules Involved:  
* app/api/folders/\[folderId\]/route.ts  
* lib/sessionUtils.ts, lib/prisma.ts, zod  
  Testing Considerations (Technical): Test renaming folder. Test validation. Test ownership check (404). Test unique name constraint (409). Test auth (401).  
  Dependencies (Technical): KC-40, KC-8.2

Ticket ID: KC-42.3  
Title: Create API endpoint to Delete Folder  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-2  
Team: BE  
Dependencies (Functional): KC-40 (Folder Schema), KC-8.2 (Auth Check)  
UX/UI Design Link: N/A  
Description (Functional): Implement the backend logic to delete an existing folder, ensuring user ownership and handling constraints (e.g., preventing deletion of non-empty folders initially).  
Acceptance Criteria (Functional):

* Sending a DELETE request to /api/folders/{folderId} deletes the folder if it exists, belongs to the user, AND is empty (contains no cards or sub-folders).  
* Returns success (200 or 204\) on successful deletion.  
* Returns 404 if folder not found or not owned.  
* Returns 401 if user not logged in.  
* Returns 400 Bad Request if the folder is not empty (contains cards or sub-folders). Include a specific error message.  
* (Schema onDelete: Cascade handles deletion of nested children folders automatically if parent is deleted).  
  Technical Approach / Implementation Notes:  
* In app/api/folders/\[folderId\]/route.ts, export async function DELETE(request: Request, { params }: { params: { folderId: string } }).  
* Import NextResponse, prisma, getCurrentUserId.  
* Validate params.folderId format (400 if invalid).  
* const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }  
* Use try/catch.  
* **Check ownership and emptiness:**  
  const folderToDelete \= await prisma.folder.findUnique({  
    where: { id: params.folderId, userId: userId },  
    include: {  
      \_count: { // Use select with \_count for efficiency  
        select: { cards: true, children: true }  
      }  
    }  
  });

  if (\!folderToDelete) {  
    return NextResponse.json({ error: 'Folder not found' }, { status: 404 });  
  }

  if (folderToDelete.\_count.cards \> 0 || folderToDelete.\_count.children \> 0\) {  
    return NextResponse.json({ error: 'Folder is not empty. Cannot delete.' }, { status: 400 });  
  }

* Delete the folder: await prisma.folder.delete({ where: { id: params.folderId } });  
* Return NextResponse.json({ message: 'Folder deleted successfully' }, { status: 200 }); (or 204).  
* Handle Prisma errors (500).  
  API Contract (if applicable):  
* **Endpoint:** DELETE /api/folders/{folderId}  
* **Request:** URL parameter folderId. Auth via session.  
* **Response Success (200):** { message: 'Folder deleted successfully' } or **(204)** No Content.  
* **Response Error (400):** { error: 'Folder is not empty. Cannot delete.' } or { error: 'Invalid folder ID format' }  
* **Response Error (401):** { error: 'Unauthorized' }  
* **Response Error (404):** { error: 'Folder not found' }  
* Response Error (500): { error: 'Internal server error' }  
  Data Model Changes (if applicable): Deletes Folder record (and potentially children due to cascade).  
  Key Functions/Modules Involved:  
* app/api/folders/\[folderId\]/route.ts  
* lib/sessionUtils.ts, lib/prisma.ts  
  Testing Considerations (Technical): Test deleting empty folder. Test deleting non-empty folder (expect 400). Test ownership check (404). Test auth (401). Test cascade delete effect on children (if applicable).  
  Dependencies (Technical): KC-40, KC-8.2

Ticket ID: KC-44  
Title: Create API endpoint to Move Card to Folder  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-3  
Team: BE  
Dependencies (Functional): KC-20.1-BLOCK (Card Schema), KC-40 (Folder Schema), KC-8.2 (Auth Check)  
UX/UI Design Link: N/A  
Description (Functional): Allow users to assign or unassign a card to/from a specific folder by updating the card's folder association.
Acceptance Criteria (Functional):
* The system allows updating the `folderId` field on a Card record.
* Sending a PUT request to the card update endpoint (`/api/cards/{cardId}`) with a valid `folderId` (or `null`) updates the card's association.
* The system prevents associating a card with a folder that does not exist or is not owned by the user.
Technical Approach / Implementation Notes:
* **Modify existing Card Update API:** Update the PUT handler in `app/api/cards/[cardId]/route.ts` (from KC-CARD-BE-2-BLOCK).
* **Update Request Schema:** Add `folderId: z.string().cuid().optional().nullable()` to the Zod schema (`UpdateCardSchema`) used for validating the PUT request body.
* **Add Target Folder Ownership Check:**
  * Inside the PUT handler, after validating the request and checking ownership of the *card*.
  * If `validation.data.folderId` is present (not null):
    * Query `prisma.folder.findUnique({ where: { id: validation.data.folderId, userId: userId } });`.
    * If the target folder is not found or not owned by the user, return a 400 Bad Request error (e.g., { error: "Target folder not found or not owned" }).
* **Update Prisma Call:** Ensure the `data` object passed to `prisma.card.update` includes the validated `folderId` (which could be null to move to root).
API Contract (if applicable):
* **Modify Endpoint:** PUT /api/cards/{cardId}
* **Update Request Body:** Add optional field `folderId?: string | null`.
* **Update Response Errors:** Add potential 400 error for invalid/non-owned target `folderId`.
Data Model Changes (if applicable): N/A (Uses existing Card.folderId relation from KC-20.1-BLOCK/KC-40).
Key Functions/Modules Involved:
* `app/api/cards/[cardId]/route.ts`
* Zod schema for card updates.
* Prisma client (`prisma.folder.findUnique`, `prisma.card.update`).
Testing Considerations (Technical): Test moving a card into a folder, moving a card back to root (null folderId). Test attempting to move to a non-existent folder (400). Test attempting to move to a folder owned by another user (400). Verify card ownership check still functions correctly. Ensure other card update fields (title, content, tags) still work alongside folder moves.
Dependencies (Technical): KC-40, KC-CARD-BE-2-BLOCK, KC-8.2

Ticket ID: KC-ORG-FE-1  
Title: Implement Folder Tree Display Component  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-1  
Team: FE  
Dependencies (Functional): KC-ORG-BE-1 (List API), KC-ORG-UX-1 (Design), KC-SETUP-3 (Chakra UI)  
UX/UI Design Link: \[Link to Figma/mockups for Folder Tree\]  
Description (Functional): Create a reusable frontend component that fetches the user's folders and displays them in a hierarchical tree structure, allowing expansion and collapse.  
Acceptance Criteria (Functional):

* Component fetches folder data from GET /api/folders on mount.  
* Displays folders in a nested tree view based on parentId.  
* Root-level folders are displayed at the top level.  
* Clicking an expand/collapse icon next to a folder with children toggles the visibility of its children.  
* The component handles loading and error states during data fetching.  
* Matches the visual design from KC-ORG-UX-1.  
* (Optional Stage 1+) Highlights the currently selected folder.  
  Technical Approach / Implementation Notes:  
* Create src/components/folders/FolderTree.tsx. Mark as 'use client'.  
* Import useEffect, useState, Chakra components (Box, VStack, Text, IconButton, Spinner), icons (e.g., ChevronRightIcon, ChevronDownIcon from @chakra-ui/icons).  
* Use useState for folders: Folder\[\], tree: TreeNode\[\], isLoading, error. (Define Folder and TreeNode types).  
* Fetch flat list from /api/folders in useEffect.  
* **Tree Building:** Implement a utility function buildTree(folders: Folder\[\]): TreeNode\[\] that takes the flat list and converts it into a nested structure (e.g., TreeNode { id, name, children: TreeNode\[\] }). This function will likely involve creating a map of folders by ID and then iterating to link children to parents.  
* Store the built tree in state (setTree(buildTree(fetchedFolders))).  
* **Recursive Rendering:** Create a sub-component FolderTreeNode.tsx that takes a node: TreeNode prop.  
  * Render the folder name (node.name).  
  * Include expand/collapse IconButton if node.children.length \> 0\. Use useState within this component to manage its own isOpen state.  
  * Conditionally render children by mapping node.children and recursively calling \<FolderTreeNode node={child} /\> if isOpen. Apply indentation (paddingLeft).  
* In FolderTree.tsx, map over the top-level nodes of the tree state and render \<FolderTreeNode /\> for each.  
* Handle loading/error states appropriately.  
  API Contract (if applicable): Consumes GET /api/folders (KC-ORG-BE-1).  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/components/folders/FolderTree.tsx  
* src/components/folders/FolderTreeNode.tsx (Recursive component)  
* lib/folderUtils.ts (Optional: buildTree function)  
* React useState, useEffect, fetch  
* Chakra UI components  
  Testing Considerations (Technical): Unit test buildTree function. Unit test FolderTreeNode rendering (with/without children, expanded/collapsed). Unit test FolderTree data fetching and rendering based on mocked API response.  
  Dependencies (Technical): KC-ORG-BE-1, KC-ORG-UX-1, KC-SETUP-3

Ticket ID: KC-ORG-FE-5 (Generated)  
Title: Integrate Folder Tree into Sidebar/Layout  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-1  
Team: FE  
Dependencies (Functional): KC-ORG-FE-1 (FolderTree Comp), KC-AUTH-FE-4 (Layout Structure)  
UX/UI Design Link: \[Link to Figma/mockups showing Sidebar\]  
Description (Functional): Place the Folder Tree component into the main application layout, typically within a collapsible or fixed sidebar, allowing users to navigate their folders.  
Acceptance Criteria (Functional):

* The FolderTree component is rendered within a designated sidebar area in the main application layout for logged-in users.  
* The sidebar layout functions correctly (e.g., collapsible if designed).  
* The folder tree is visible and interactive alongside the main content area.  
  Technical Approach / Implementation Notes:  
* Modify the main layout component (e.g., potentially within src/app/(protected)/layout.tsx or a dedicated sidebar component imported there).  
* Use Chakra UI layout components (Flex, Box, Drawer for collapsible sidebar) to structure the layout with a sidebar and main content area.  
* Place the \<FolderTree /\> component within the sidebar section.  
* Ensure the layout is responsive as per UX design.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/app/(protected)/layout.tsx (or similar layout file)  
* src/components/layout/Sidebar.tsx (Optional dedicated component)  
* src/components/folders/FolderTree.tsx  
* Chakra UI layout components  
  Testing Considerations (Technical): E2E test the layout to ensure sidebar and folder tree are visible and functional. Unit test the layout component structure (verify FolderTree is included).  
  Dependencies (Technical): KC-ORG-FE-1, KC-AUTH-FE-4

Ticket ID: KC-ORG-FE-2  
Title: Implement Folder Creation UI & Logic  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-2  
Team: FE  
Dependencies (Functional): KC-ORG-FE-1 (Tree interaction context), KC-42.1 (Create API), KC-ORG-UX-1 (Design)  
UX/UI Design Link: \[Link to Figma/mockups for Create Folder Modal/Input\]  
Description (Functional): Allow users to create new folders, potentially specifying a parent folder, via the UI (e.g., a button or context menu option).  
Acceptance Criteria (Functional):

* A "Create Folder" action (button, menu item) is available.  
* Invoking the action opens a modal or input field prompting for the new folder name.  
* Submitting a valid name calls the POST /api/folders endpoint (passing the appropriate parentId if creating a sub-folder).  
* The folder tree updates automatically to show the new folder on success.  
* Loading state and error messages (validation, name conflict, API errors) are handled.  
  Technical Approach / Implementation Notes:  
* Add a "Create Folder" button (e.g., above the tree) or context menu integration to FolderTree / FolderTreeNode.  
* Use Chakra UI Modal or Popover with an Input field and Save/Cancel buttons.  
* Use useState to manage modal visibility, input value, loading state, error state.  
* Need a way to determine the parentId (null for root, or the ID of the folder where the "create" action was initiated). This might involve passing context down the tree or using a state management solution.  
* Implement handleSaveFolder:  
  * Validate input name.  
  * setIsLoading(true);  
  * fetch('/api/folders', { method: 'POST', ..., body: JSON.stringify({ name: folderName, parentId: targetParentId }) });  
  * On success: Close modal, show toast, **refresh the folder list/tree data** (e.g., by calling the fetch function again or using a state management library like Zustand).  
  * On failure (400, 409, 500): Show error message in the modal or via toast.  
  * setIsLoading(false);  
* **State Management:** Fetching/managing folder data might become complex. Consider introducing Zustand (KC-SETUP-3) here:  
  * Create src/stores/folderStore.ts.  
  * Store folders: Folder\[\], isLoading, error.  
  * Define actions: fetchFolders, addFolder.  
  * fetchFolders: Calls API, updates state.  
  * addFolder: Calls POST API, on success calls fetchFolders again to refresh.  
  * Components (FolderTree, Create Modal) would use this store instead of local state for folder data.  
    API Contract (if applicable): Consumes POST /api/folders (KC-42.1).  
    Data Model Changes (if applicable): N/A  
    Key Functions/Modules Involved:  
* src/components/folders/FolderTree.tsx (trigger)  
* src/components/folders/CreateFolderModal.tsx (or similar UI)  
* React useState, fetch  
* Chakra UI Modal, Input, Button  
* (Recommended) src/stores/folderStore.ts (Zustand store)  
  Testing Considerations (Technical): Unit test modal component, handleSaveFolder logic (mocking fetch, store actions). E2E test creating root and nested folders. Test error handling (name conflict).  
  Dependencies (Technical): KC-ORG-FE-1, KC-42.1, KC-ORG-UX-1, (Optional) Zustand setup

Ticket ID: KC-ORG-FE-3  
Title: Implement Folder Rename UI & Logic  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-2  
Team: FE  
Dependencies (Functional): KC-ORG-FE-1 (Tree interaction context), KC-42.2 (Update API), KC-ORG-UX-1 (Design)  
UX/UI Design Link: \[Link to Figma/mockups for Rename Folder\]  
Description (Functional): Allow users to rename existing folders via the UI (e.g., context menu option leading to a modal or inline editing).  
Acceptance Criteria (Functional):

* A "Rename" action is available for each folder in the tree (e.g., context menu).  
* Invoking the action allows editing the folder name (e.g., in a modal or inline input pre-filled with the current name).  
* Submitting a valid new name calls the PUT /api/folders/{folderId} endpoint.  
* The folder tree updates automatically to show the renamed folder on success.  
* Loading state and error messages (validation, name conflict, API errors) are handled.  
  Technical Approach / Implementation Notes:  
* Add "Rename" option to context menu in FolderTreeNode.  
* On "Rename" click, open a Modal (similar to Create) pre-filled with the current folder name, or implement inline editing logic within FolderTreeNode.  
* Use useState for modal/edit state, input value, loading, error.  
* Implement handleRenameFolder:  
  * Validate new name.  
  * setIsLoading(true);  
  * fetch(\\/api/folders/${folderId}\`, { method: 'PUT', ..., body: JSON.stringify({ name: newName }) });\`  
  * On success: Close modal/finish inline edit, show toast, refresh folder list/tree (call fetchFolders from store).  
  * On failure (400, 404, 409, 500): Show error message.  
  * setIsLoading(false);  
* Use Zustand store (folderStore) for data refresh. Add renameFolder action to store.  
  API Contract (if applicable): Consumes PUT /api/folders/{folderId} (KC-42.2).  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/components/folders/FolderTreeNode.tsx (trigger/inline edit)  
* src/components/folders/RenameFolderModal.tsx (Optional)  
* React useState, fetch  
* Chakra UI Modal, Input, Button  
* src/stores/folderStore.ts (Zustand store)  
  Testing Considerations (Technical): Unit test rename modal/inline edit logic, handleRenameFolder (mock fetch, store). E2E test renaming a folder. Test error handling (name conflict).  
  Dependencies (Technical): KC-ORG-FE-1, KC-42.2, KC-ORG-UX-1, Zustand store

Ticket ID: KC-ORG-FE-4  
Title: Implement Folder Deletion UI & Logic  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-2  
Team: FE  
Dependencies (Functional): KC-ORG-FE-1 (Tree interaction context), KC-42.3 (Delete API), KC-ORG-UX-1 (Design)  
UX/UI Design Link: \[Link to Figma/mockups for Delete Folder Confirmation\]  
Description (Functional): Allow users to delete existing folders via the UI, including a confirmation step that warns if the folder is not empty (based on API response).  
Acceptance Criteria (Functional):

* A "Delete" action is available for each folder in the tree (e.g., context menu).  
* Invoking the action prompts for confirmation using an AlertDialog.  
* Confirming deletion calls the DELETE /api/folders/{folderId} endpoint.  
* If the API returns an error indicating the folder is not empty (400), display this specific message to the user.  
* The folder tree updates automatically to remove the folder on successful deletion.  
* Loading state is shown during the API call.  
  Technical Approach / Implementation Notes:  
* Add "Delete" option to context menu in FolderTreeNode.  
* On "Delete" click, open Chakra UI AlertDialog (similar to KC-CARD-FE-5-BLOCK).  
* Use useState for isDeleting state.  
* Implement handleDeleteFolderConfirm:  
  * setIsDeleting(true);  
  * fetch(\\/api/folders/${folderId}\`, { method: 'DELETE' });\`  
  * On success (response.ok): Close dialog, show toast, refresh folder list/tree (call fetchFolders from store).  
  * On failure:  
    * If response.status \=== 400: Parse error message (e.g., "Folder is not empty"), display specific error toast/message.  
    * Handle other errors (401, 404, 500\) with generic error message.  
  * setIsDeleting(false); (May stay in dialog on specific errors like 400).  
* Use Zustand store (folderStore) for data refresh. Add deleteFolder action.  
  API Contract (if applicable): Consumes DELETE /api/folders/{folderId} (KC-42.3).  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* src/components/folders/FolderTreeNode.tsx (trigger)  
* Chakra UI AlertDialog, useDisclosure, Button, useToast  
* React useState, fetch  
* src/stores/folderStore.ts (Zustand store)  
  Testing Considerations (Technical): Unit test confirmation dialog logic, handleDeleteFolderConfirm (mock fetch, store), especially handling of 400 error. E2E test deleting an empty folder and attempting to delete a non-empty folder.  
  Dependencies (Technical): KC-ORG-FE-1, KC-42.3, KC-ORG-UX-1, Zustand store

Ticket ID: KC-ORG-FE-6 (Generated)  
Title: Implement Move Card to Folder UI Logic  
Epic: KC-ORG  
PRD Requirement(s): FR-ORG-3  
Team: FE  
Dependencies (Functional): KC-44 (Move API \- via Card Update), KC-ORG-FE-1 (Folder Tree for target selection or DND), KC-CARD-FE-3-BLOCK / KC-CARD-FE-6-BLOCK (Card context)  
UX/UI Design Link: \[Link to Figma/mockups for Move Card Interaction\]  
Description (Functional): Allow users to move a card into a specific folder using a UI interaction like drag-and-drop or a "Move to" menu.  
Acceptance Criteria (Functional):

* User can initiate moving a card (e.g., drag card from list, click "Move to" button on card).  
* User can select a target folder (e.g., drop onto folder in tree, select from a dropdown/modal).  
* The action calls the PUT /api/cards/{cardId} endpoint with the folderId of the target folder (or null if moving to root).  
* UI updates to reflect the card's new location (e.g., card list might refresh or re-filter if filtered by folder).  
* Loading state and errors are handled.  
  Technical Approach / Implementation Notes:  
* **Option A (Drag and Drop):**  
  * Requires a DND library (e.g., react-beautiful-dnd, @dnd-kit/core).  
  * Make card list items draggable (Draggable).  
  * Make folder tree nodes droppable (Droppable).  
  * Implement onDragEnd handler: Get dragged cardId and destination folderId. Call handleMoveCard(cardId, folderId).  
* **Option B ("Move to" Button/Menu):**  
  * Add a "Move to" button/menu item to the card component (in list or display page).  
  * Clicking it opens a Modal or Menu displaying the folder tree (or a simplified list/dropdown).  
  * Selecting a folder (or "Root") triggers handleMoveCard(cardId, selectedFolderId).  
* **handleMoveCard(cardId, folderId)** function:  
  * setIsLoading(true);  
  * fetch(\\/api/cards/${cardId}\`, { method: 'PUT', ..., body: JSON.stringify({ folderId: folderId }) });\` // Use API from KC-44  
  * On success: Show toast, potentially refresh card list or folder view.  
  * On failure: Show error toast.  
  * setIsLoading(false);  
* State management (Zustand) might be needed to coordinate updates between card lists and folder tree if filtering is active.  
  API Contract (if applicable): Consumes PUT /api/cards/{cardId} (KC-44).  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Card list component (KC-CARD-FE-6-BLOCK) / Card display component (KC-CARD-FE-3-BLOCK)  
* Folder tree component (KC-ORG-FE-1)  
* (Option A) DND library components and handlers.  
* (Option B) Chakra UI Modal / Menu.  
* handleMoveCard utility function.  
* fetch.  
  Testing Considerations (Technical): E2E test moving a card into a folder and to root using the chosen method (DND or button). Unit test handleMoveCard logic. Test UI states (loading, error).  
  Dependencies (Technical): KC-44, KC-ORG-FE-1, KC-CARD-FE-3-BLOCK / KC-CARD-FE-6-BLOCK, (Optional) DND library.

Ticket ID: KC-ORG-TEST-BE-1 (Generated)  
Title: Write Unit Tests for Folder API Logic  
Epic: KC-ORG  
PRD Requirement(s): NFR-MAINT-1  
Team: BE/QA  
Dependencies (Functional): KC-ORG-BE-1, KC-42.1, KC-42.2, KC-42.3, KC-44 (Card move logic), KC-72 (Auth Test Setup)  
UX/UI Design Link: N/A  
Description (Functional): Create automated unit tests for the backend API endpoints related to Folder CRUD operations and moving cards between folders.  
Acceptance Criteria (Functional):

* Tests cover successful listing, creation, renaming, and deletion of folders, mocking DB interactions.  
* Tests verify ownership checks for all operations.  
* Tests verify validation logic (name, parentId).  
* Tests verify unique name constraints (create/rename).  
* Tests verify deletion constraint (non-empty folder check).  
* Tests verify card move logic (updating Card.folderId via PUT card endpoint) including target folder ownership check.  
* Tests cover error handling scenarios (400, 401, 404, 409, 500).  
  Technical Approach / Implementation Notes:  
* Use Jest/Vitest. Create test files src/app/api/folders/route.test.ts and src/app/api/folders/\[folderId\]/route.test.ts. Also add tests for folder logic in src/app/api/cards/\[cardId\]/route.test.ts (for KC-44).  
* **Mock Dependencies:** Mock Prisma Client (prisma.folder.\*, prisma.card.update), mock getCurrentUserId.  
* **Test GET /api/folders (List):** Test success (flat/nested), empty, auth.  
* **Test POST /api/folders (Create):** Test success (root/nested), validation, parent ownership, name conflict (409), auth.  
* **Test PUT /api/folders/{folderId} (Rename):** Test success, validation, ownership, name conflict (409), auth.  
* **Test DELETE /api/folders/{folderId} (Delete):** Test success (empty), non-empty (400), ownership, auth.  
* **Test PUT /api/cards/{cardId} (Move Card \- KC-44 logic):**  
  * Mock prisma.card.findUnique (for card ownership).  
  * Mock prisma.folder.findUnique (for target folder ownership).  
  * Mock prisma.card.update.  
  * Test moving to valid folder, moving to root (null), moving to non-owned folder (400), moving non-owned card (404).  
    API Contract (if applicable): N/A  
    Data Model Changes (if applicable): N/A  
    Key Functions/Modules Involved:  
* API route handlers for folders and card updates.  
* Jest/Vitest, mocks.  
  Testing Considerations (Technical): Structure tests clearly. Reset mocks. Test edge cases like root folders (parentId: null).  
  Dependencies (Technical): All Folder BE tickets, KC-44, Testing framework setup.

Ticket ID: KC-ORG-TEST-FE-1  
Title: Write Unit Tests for Folder UI Components  
Epic: KC-ORG  
PRD Requirement(s): NFR-MAINT-1  
Team: FE/QA  
Dependencies (Functional): KC-ORG-FE-1 to KC-ORG-FE-6, KC-TEST-FE-1  
UX/UI Design Link: N/A  
Description (Functional): Create automated unit tests for key frontend components related to folder management (tree display, create/rename/delete modals/interactions, move card interactions).  
Acceptance Criteria (Functional):

* Unit tests exist for FolderTree and FolderTreeNode (rendering, expansion/collapse, tree building logic if applicable).  
* Unit tests exist for Create/Rename/Delete folder modals/interactions (form handling, API call logic).  
* Unit tests exist for Move Card UI logic (DND handlers or "Move to" modal/menu logic, API call).  
* Tests mock API calls (fetch), router/toast interactions, and state management store (Zustand) actions/state.  
  Technical Approach / Implementation Notes:  
* Use Jest & React Testing Library. Create test files alongside components.  
* Use test utility (renderWithProviders).  
* **Mock Zustand Store:** Use jest.mock to provide mock implementations of store actions (fetchFolders, addFolder, etc.) and selectors.  
* **FolderTree/Node** Tests: Test rendering of nested structure based on mock data. Test expand/collapse logic. Test context menu trigger (if applicable).  
* **Create/Rename/Delete Modal/Interaction Tests:**  
  * Mock fetch. Mock store actions. Mock useToast.  
  * Test modal opening/closing. Test form input/validation.  
  * Simulate save/confirm action. Assert fetch called correctly. Assert store refresh action called on success. Assert error handling.  
* **Move Card UI Tests:**  
  * Mock fetch. Mock store actions (if needed). Mock useToast.  
  * (DND): Mock DND context/library hooks. Simulate drag end event. Assert fetch called with correct cardId/folderId.  
  * ("Move to"): Test modal/menu opening. Simulate folder selection. Assert fetch called correctly.  
    API Contract (if applicable): N/A  
    Data Model Changes (if applicable): N/A  
    Key Functions/Modules Involved:  
* Folder UI component test files.  
* Jest, React Testing Library, mocks for fetch, store, router, toast, DND lib.  
  Testing Considerations (Technical): Mocking the Zustand store and DND interactions can be complex; focus on testing the component's logic in response to mocked events/state.  
  Dependencies (Technical): All Folder FE tickets, KC-TEST-FE-1, Zustand store setup.

Ticket ID: KC-ORG-TEST-BE-1
Title: Write Unit/Integration Tests for Folder API Logic
Epic: KC-ORG
PRD Requirement(s): NFR-MAINT-1
Team: BE/QA
Dependencies (Functional): Folder CRUD APIs (KC-ORG-BE-1, KC-42.1, KC-42.2, KC-42.3), Card Move API (KC-44), KC-TEST-BE-1
UX/UI Design Link: N/A
Description (Functional): Create automated unit and integration tests for the backend API endpoints related to folder management (CRUD, list) and moving cards between folders.
Acceptance Criteria (Functional):
* Tests verify successful folder listing (GET /api/folders), creation (POST /api/folders), renaming (PUT /api/folders/{folderId}), and deletion (DELETE /api/folders/{folderId}).
* Tests verify the logic for moving cards (PUT /api/cards/{cardId} with folderId) including target folder ownership checks.
* Tests cover validation errors (e.g., missing name, invalid parentId), auth errors (401), ownership errors (404), name conflicts (409), preventing deletion of non-empty folders (400), and DB errors (500).
Technical Approach / Implementation Notes:
* Use Jest/Vitest and Supertest.
* Interact with a test database, seeding user, folder (nested), and card data.
* Mock `getCurrentUserId`.
* Test cases for each Folder API: Success (root/nested), validation, auth, ownership, conflicts, non-empty delete.
* Test cases for Card Move API: Success (move to folder, move to root), validation (invalid folderId), target folder ownership failure.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `/app/api/folders/route.ts`, `/app/api/folders/[folderId]/route.ts`, `/app/api/cards/[cardId]/route.ts` (relevant part), Test framework, Test DB utilities.
Testing Considerations (Technical): Thoroughly test nested folder creation/deletion, name uniqueness constraint (@@unique([userId, parentId, name])), and the non-empty delete check.
Dependencies (Technical): All Folder BE tickets, KC-44, KC-TEST-BE-1

Ticket ID: KC-ORG-TEST-FE-1
Title: Write Unit/Integration Tests for Folder UI Components
Epic: KC-ORG
PRD Requirement(s): NFR-MAINT-1
Team: FE/QA
Dependencies (Functional): Folder UI Components/Pages (KC-ORG-FE-1 to 6), KC-TEST-FE-1, Zustand Store (if used)
UX/UI Design Link: N/A
Description (Functional): Create automated unit and integration tests for the frontend components related to folder display (tree), creation, renaming, deletion, and moving cards.
Acceptance Criteria (Functional):
* Unit tests verify rendering and basic interaction logic of `FolderTree`, `FolderTreeNode`, Create/Rename/Delete modals.
* Unit tests verify `buildTree` utility function correctly transforms flat list to tree.
* Integration tests verify folder tree displays data fetched via store action.
* Integration tests verify create/rename/delete interactions: opening modals, form submission triggers store actions, store actions trigger API mocks, success/error handling updates UI (via store refresh).
* Integration tests verify the chosen card move interaction (DND or Menu) triggers the correct API call mock.
* Tests cover loading and error states for store actions/API interactions.
Technical Approach / Implementation Notes:
* Use Jest/Vitest and React Testing Library.
* Mock Zustand store actions (`fetchFolders`, `addFolder`, `renameFolder`, `deleteFolder`) or API fetch calls directly if not using Zustand.
* Mock `fetch` for card move API call.
* Mock `useRouter`, `useToast`, DND library hooks (if applicable).
* Simulate user interactions (clicks, drags, form inputs).
* Assert component rendering, store action calls/API call mocks, state changes, toasts.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: Folder components (`FolderTree`, `FolderTreeNode`, modals), Card list/item component (for move interaction), `folderStore.ts` (mocked if used), Mocked hooks/fetch/DND.
Testing Considerations (Technical): Focus on testing component logic and interaction with mocked store/API layer. Verify state updates correctly reflect in the UI after simulated actions.
Dependencies (Technical): All Folder FE tickets, KC-TEST-FE-1