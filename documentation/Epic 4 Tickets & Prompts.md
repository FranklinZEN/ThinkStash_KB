# **Review and AI Prompts for KC-ORG Epic (Stage 1\)**

This document contains the technical review and AI development prompts for the KC-ORG epic (Stage 1), focusing on implementing basic folder management for organizing knowledge cards.

## **Part 1: Tech Lead Review of KC-ORG Epic (Stage 1\)**

This epic introduces the foundational features for organizing cards into a hierarchical folder structure. It covers the backend schema, APIs for folder CRUD and listing, logic for moving cards into folders, and the corresponding frontend UI, primarily a folder tree display.

**A. Alignment and Coverage:**

* **PRD/TDD/ADRs:** Tickets align with PRD requirements (FR-ORG-1, 2, 3\) and build upon existing architecture (Next.js, Prisma, Chakra UI, NextAuth.js).  
* **Completeness:** The epic covers the necessary steps for basic folder management: UX design, schema definition, backend APIs (CRUD, list, move card), frontend components (tree display, interaction logic), and testing.

**B. Key Technical Points & Considerations:**

* **Schema Design (KC-40):**  
  * Introduces a Folder model with a self-referencing relation (parentId, children) to enable nesting.  
  * Includes onDelete: Cascade for the user and parent relationships, meaning deleting a user deletes their folders, and deleting a parent folder deletes its children. This is a significant behavior to be aware of.  
  * Includes onDelete: SetNull for the Card-Folder relationship, so deleting a folder makes cards within it orphaned (folderId becomes null) rather than deleting the cards.  
  * A crucial @@unique(\[userId, parentId, name\]) constraint prevents duplicate folder names within the same level for a given user. Error handling for this constraint (409 Conflict) is necessary in create/rename APIs.  
* **API Design:**  
  * **List Folders (KC-ORG-BE-1):** Offers two approaches for returning the folder structure (flat list vs. nested tree). The recommendation is to return a **flat list** for Stage 1 simplicity, leaving tree construction to the frontend.  
  * **Folder CRUD (KC-42.1, KC-42.2, KC-42.3):** Standard REST endpoints for creating, renaming (PUT), and deleting folders. Includes necessary ownership checks and validation.  
  * **Delete Constraint (KC-42.3):** Implements a check to prevent deleting non-empty folders (containing cards or sub-folders) using \_count in Prisma for efficiency. Returns a 400 Bad Request in this case.  
  * **Move Card (KC-44):** Cleverly integrated into the existing PUT /api/cards/{cardId} endpoint (from **KC-CARD-BE-2-BLOCK**) by allowing the folderId (nullable CUID) to be updated in the request body. Requires adding target folder ownership validation within that endpoint.  
* **Frontend Implementation:**  
  * **Folder Tree (KC-ORG-FE-1):** Requires building a tree structure from the flat API response and likely using a recursive component (FolderTreeNode) for rendering. Managing expand/collapse state is key.  
  * **State Management (KC-ORG-FE-2, 3, 4):** Creating, renaming, or deleting folders requires updating the folder tree UI reliably. The tickets explicitly recommend introducing a state management library like **Zustand** (src/stores/folderStore.ts) to handle fetching, caching, and updating folder data centrally, simplifying component logic. Prompts for relevant FE tickets incorporate this recommendation.  
  * **Move Card UI (KC-ORG-FE-6):** Presents two common UI patterns (Drag-and-Drop or "Move to" Menu/Modal) and requires implementing the chosen pattern to call the card update API. DND adds library dependencies and complexity.

**C. Potential Gaps/Refinements:**

* **Folder Filtering:** While the UX design ticket mentions specifying how folder selection filters the main card view, there isn't a dedicated backend/frontend ticket in this epic to *implement* the filtering of the card list (GET /api/cards) based on the selected folder. This filtering logic will likely be needed in a subsequent epic or added to KC-CARD-BE-4-BLOCK / KC-CARD-FE-6-BLOCK.  
* **Root Folder Representation:** UI needs to handle the concept of "root" or "uncategorized" cards (where folderId is null) distinctly from cards within specific folders.  
* **Performance:** For very large numbers of folders, fetching the entire flat list and building the tree on the frontend might become slow. This is acceptable for Stage 1 but may need optimization later (e.g., fetching children on demand).

**D. Implicit Decisions:**

* Folder hierarchy is managed via a self-referencing relational model.  
* A flat list API is preferred for initial folder fetching.  
* Card moving is handled by updating the card's folderId via the existing card update endpoint.  
* Zustand is recommended for frontend state management of folder data.

This epic lays the groundwork for organizing content. The schema design choices (especially onDelete behaviors) and the recommendation for Zustand are important considerations during implementation. Implementing the card list filtering based on folder selection is a likely next step.

## **Part 2: AI Development Prompts for KC-ORG Epic (Stage 1\)**

*(Prompts reference the full suite of project documents and incorporate review findings)*

**1\. Ticket: KC-ORG-UX-1: Design Folder Management UI & Interactions**

* **Prompt (For TL/Dev Reference):** Review and finalize the UX designs for folder management as specified in **JIRA Ticket KC-ORG-UX-1**. Ensure designs:  
  * Detail the hierarchical folder tree display (sidebar, indentation, icons).  
  * Specify interactions for Create, Rename, Delete (context menus, modals/dialogs using Chakra UI).  
  * Define how folder selection filters the card view (visual state, though implementation is likely post-Stage 1).  
  * Detail card moving interactions (DND specification or "Move to" menu flow).  
  * Include confirmation dialogs, error states, responsiveness, and accessibility.  
  * These designs guide **KC-ORG-FE-1** through **KC-ORG-FE-6**.

**2\. Ticket: KC-40: Define Folder Schema in Prisma**

* **Prompt:** Update the Prisma schema (prisma/schema.prisma) to define the Folder model for hierarchical organization, as specified in **JIRA Ticket KC-40**.  
  1. Define model Folder with fields: id (String, cuid, id), name (String), createdAt (DateTime, default now), updatedAt (DateTime, updatedAt).  
  2. Add userId (String) and relation user User @relation(fields: \[userId\], references: \[id\], onDelete: Cascade).  
  3. Add self-relation for nesting: parentId (String?), parent Folder? @relation("FolderHierarchy", fields: \[parentId\], references: \[id\], onDelete: Cascade), children Folder\[\] @relation("FolderHierarchy"). **Note the onDelete: Cascade for parent.**  
  4. Add relation to cards: cards Card\[\].  
  5. Add unique constraint: @@unique(\[userId, parentId, name\]).  
  6. Add indexes: @@index(\[userId\]), @@index(\[parentId\]).  
  7. Verify the folderId / folder relation exists on the Card model (**KC-20.1-BLOCK**) with onDelete: SetNull.  
  8. Run npx prisma migrate dev \--name add-folder-model.  
  9. Run npx prisma generate.

**3\. Ticket: KC-ORG-BE-1: Create API endpoint to List Folders (Tree Structure)**

* **Prompt:** Implement the GET /api/folders endpoint to retrieve the user's folders as a flat list, as specified in **JIRA Ticket KC-ORG-BE-1**.  
  1. Create app/api/folders/route.ts. Export async GET(request: Request).  
  2. Import NextResponse, prisma, getCurrentUserId (**KC-8.2**).  
  3. Auth check: const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }.  
  4. Use try/catch.  
  5. Fetch **all** folders for the user as a **flat list**: const folders \= await prisma.folder.findMany({ where: { userId: userId }, select: { id: true, name: true, parentId: true, updatedAt: true }, orderBy: { name: 'asc' } });. Select only fields needed for tree building/display.  
  6. Return the flat folders array: return NextResponse.json(folders);. (Frontend will build the tree).  
  7. Handle Prisma/other errors (500).  
  8. Write integration tests (**KC-ORG-TEST-BE-1**) covering success (flat list), empty list, and auth error.

**4\. Ticket: KC-42.1: Create API endpoint to Create Folder**

* **Prompt:** Implement the POST /api/folders endpoint to create new folders, as specified in **JIRA Ticket KC-42.1**.  
  1. In app/api/folders/route.ts, export async POST(request: Request).  
  2. Import NextResponse, prisma, getCurrentUserId, zod.  
  3. Define CreateFolderSchema \= z.object({ name: z.string().min(1), parentId: z.string().cuid().optional().nullable() });.  
  4. Auth check: const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }.  
  5. Parse and validate body: const validation \= CreateFolderSchema.safeParse(await request.json()); if (\!validation.success) { /\* 400 \*/ }.  
  6. Use try/catch.  
  7. **Validate parentId ownership if provided:** If validation.data.parentId, check await prisma.folder.findUnique({ where: { id: validation.data.parentId, userId: userId } });. If not found, return 400 error ("Parent folder not found or not owned").  
  8. Create folder: const newFolder \= await prisma.folder.create({ data: { name, userId, parentId } });.  
  9. Return NextResponse.json(newFolder, { status: 201 });.  
  10. **Handle unique constraint violation in catch block:** Check for Prisma error code P2002. If matched, return NextResponse.json({ error: 'Folder name already exists at this level' }, { status: 409 });.  
  11. Handle other errors (500).  
  12. Write integration tests (**KC-ORG-TEST-BE-1**) covering success (root/nested), validation, parent ownership check, name conflict (409), auth error.

**5\. Ticket: KC-42.2: Create API endpoint to Update Folder (Rename)**

* **Prompt:** Implement the PUT /api/folders/{folderId} endpoint to rename folders, as specified in **JIRA Ticket KC-42.2**.  
  1. Create app/api/folders/\[folderId\]/route.ts. Export async PUT(request: Request, { params }: { params: { folderId: string } }).  
  2. Import NextResponse, prisma, getCurrentUserId, zod.  
  3. Validate params.folderId format (400 if invalid).  
  4. Define UpdateFolderSchema \= z.object({ name: z.string().min(1) });.  
  5. Auth check: const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }.  
  6. Parse and validate body: const validation \= UpdateFolderSchema.safeParse(await request.json()); if (\!validation.success) { /\* 400 \*/ }.  
  7. Use try/catch.  
  8. **Ownership check:** const existingFolder \= await prisma.folder.findUnique({ where: { id: params.folderId, userId: userId } }); if (\!existingFolder) { /\* 404 \*/ }.  
  9. Update folder: const updatedFolder \= await prisma.folder.update({ where: { id: params.folderId }, data: { name: validation.data.name } });.  
  10. Return NextResponse.json(updatedFolder);.  
  11. **Handle unique constraint violation in catch block:** Check for Prisma error code P2002. If matched, return NextResponse.json({ error: 'Folder name already exists at this level' }, { status: 409 });.  
  12. Handle other errors (500).  
  13. Write integration tests (**KC-ORG-TEST-BE-1**) covering success, validation, ownership check, name conflict (409), auth error.

**6\. Ticket: KC-42.3: Create API endpoint to Delete Folder**

* **Prompt:** Implement the DELETE /api/folders/{folderId} endpoint to delete folders, preventing deletion of non-empty folders, as specified in **JIRA Ticket KC-42.3**.  
  1. In app/api/folders/\[folderId\]/route.ts, export async DELETE(request: Request, { params }: { params: { folderId: string } }).  
  2. Import NextResponse, prisma, getCurrentUserId.  
  3. Validate params.folderId format (400 if invalid).  
  4. Auth check: const userId \= await getCurrentUserId(); if (\!userId) { /\* 401 \*/ }.  
  5. Use try/catch.  
  6. **Check ownership and emptiness:**  
     const folderToDelete \= await prisma.folder.findUnique({  
       where: { id: params.folderId, userId: userId },  
       include: { \_count: { select: { cards: true, children: true } } }  
     });  
     if (\!folderToDelete) { /\* 404 \*/ }  
     if (folderToDelete.\_count.cards \> 0 || folderToDelete.\_count.children \> 0\) {  
       return NextResponse.json({ error: 'Folder is not empty.' }, { status: 400 });  
     }

  7. Delete folder: await prisma.folder.delete({ where: { id: params.folderId } });.  
  8. Return NextResponse.json({ message: 'Folder deleted' }, { status: 200 }); or NextResponse.next({ status: 204 });.  
  9. Handle Prisma/other errors (500).  
  10. Write integration tests (**KC-ORG-TEST-BE-1**) covering success (empty folder), non-empty attempt (400), ownership check (404), auth error.

**7\. Ticket: KC-44: Create API endpoint to Move Card to Folder**

* **Prompt:** Modify the existing Card Update endpoint (PUT /api/cards/{cardId}) to handle moving cards between folders, as specified in **JIRA Ticket KC-44**.  
  1. Modify app/api/cards/\[cardId\]/route.ts (from **KC-CARD-BE-2-BLOCK**).  
  2. Import zod if not already present.  
  3. Add folderId: z.string().cuid().optional().nullable() to the UpdateCardSchema used in the PUT handler.  
  4. Inside the PUT handler function:  
     * After parsing/validating the request body (validation).  
     * After the existing ownership check for the card (existingCard).  
     * **Add target folder ownership check:** If validation.data.folderId is present (and not null):  
       const targetFolder \= await prisma.folder.findUnique({  
         where: { id: validation.data.folderId, userId: userId }  
       });  
       if (\!targetFolder) {  
         return NextResponse.json({ error: 'Target folder not found or not owned' }, { status: 400 });  
       }

     * In the prisma.card.update call, ensure the data object includes folderId: validation.data.folderId if it was present in the validated request data.  
  5. Update API contract documentation for PUT /api/cards/{cardId} to reflect the optional folderId field and related 400 error.  
  6. Write/update integration tests (**KC-ORG-TEST-BE-1** / **KC-CARD-TEST-BE-1-BLOCK**) covering moving card to folder, moving to root (null), moving to non-owned/invalid folder (400), moving non-owned card (404).

**8\. Ticket: KC-ORG-FE-1: Implement Folder Tree Display Component**

* **Prompt:** Create the reusable FolderTree frontend component to display the folder hierarchy, as specified in **JIRA Ticket KC-ORG-FE-1**.  
  1. Create src/components/folders/FolderTree.tsx. Mark as 'use client'.  
  2. Import useEffect, useState, Chakra components (Box, VStack, Text, IconButton, Spinner, HStack), icons (ChevronRightIcon, ChevronDownIcon).  
  3. **State Management (Recommended):** Use Zustand store (folderStore \- see **KC-ORG-FE-2**) to fetch and hold folder data (folders: Folder\[\], isLoading, error). Define Folder type based on API response.  
  4. **Tree Building:** Create utility buildTree(folders: Folder\[\]): TreeNode\[\] (e.g., in src/lib/folderUtils.ts). Define TreeNode { id, name, children: TreeNode\[\] }. Convert flat list from store/API to nested structure. Store the result in local state (useState\<TreeNode\[\]\>(\[\])).  
  5. **Recursive Node Component:** Create src/components/folders/FolderTreeNode.tsx. Props: node: TreeNode, level: number.  
     * Use useState for isOpen.  
     * Render HStack with indentation (paddingLeft={level \* 4}).  
     * Render expand/collapse IconButton if node.children.length \> 0, toggling isOpen.  
     * Render folder node.name.  
     * Conditionally render children: If isOpen, map node.children and recursively call \<FolderTreeNode node={child} level={level \+ 1} /\>.  
  6. In FolderTree.tsx: Fetch folders using store action in useEffect. Build tree when folders data changes. Map top-level tree nodes and render \<FolderTreeNode node={node} level={0} /\>. Handle loading/error states from store.  
  7. Style according to **KC-ORG-UX-1** design.  
  8. Write unit tests (**KC-ORG-TEST-FE-1**) for buildTree, FolderTreeNode (rendering, expand/collapse), and FolderTree (fetching via mocked store, rendering tree).

**9\. Ticket: KC-ORG-FE-5: Integrate Folder Tree into Sidebar/Layout**

* **Prompt:** Integrate the FolderTree component into the main application sidebar/layout, as specified in **JIRA Ticket KC-ORG-FE-5**.  
  1. Modify the relevant layout file (e.g., src/app/(protected)/layout.tsx or a dedicated src/components/layout/Sidebar.tsx).  
  2. Use Chakra UI layout components (Flex, Box, Drawer, etc.) to define sidebar and main content areas according to **KC-ORG-UX-1** design.  
  3. Import and render the \<FolderTree /\> component (**KC-ORG-FE-1**) within the sidebar area.  
  4. Ensure layout responsiveness.  
  5. Write basic rendering tests (**KC-ORG-TEST-FE-1**) verifying FolderTree is included in the layout.

**10\. Ticket: KC-ORG-FE-2: Implement Folder Creation UI & Logic**

* **Prompt:** Implement the UI and logic for creating folders, using Zustand for state management, as specified in **JIRA Ticket KC-ORG-FE-2**.  
  1. **Zustand Store (src/stores/folderStore.ts):**  
     * Define state: folders: Folder\[\], isLoading, error.  
     * Action fetchFolders: Fetches from GET /api/folders, updates state.  
     * Action addFolder(name: string, parentId: string | null): Calls POST /api/folders, on success calls fetchFolders to refresh, handles loading/errors.  
  2. Add a "Create Folder" trigger (e.g., Button above FolderTree or context menu option in FolderTreeNode). The trigger needs context for parentId if creating a subfolder.  
  3. Create src/components/folders/CreateFolderModal.tsx (or similar). Use Chakra Modal. Props: isOpen, onClose, parentId.  
  4. Modal State: folderName, isSaving, saveError.  
  5. Modal UI: Input for name, Save/Cancel Buttons.  
  6. handleSave: Call addFolder action from folderStore. Handle loading state (isSaving). Display saveError. Close modal on success.  
  7. Connect FolderTree and trigger components to use folderStore actions/state.  
  8. Style according to **KC-ORG-UX-1**.  
  9. Write unit tests (**KC-ORG-TEST-FE-1**) for the modal and trigger, mocking store actions and testing interaction logic.

**11\. Ticket: KC-ORG-FE-3: Implement Folder Rename UI & Logic**

* **Prompt:** Implement the UI and logic for renaming folders, using Zustand, as specified in **JIRA Ticket KC-ORG-FE-3**.  
  1. **Zustand Store (folderStore):**  
     * Action renameFolder(folderId: string, newName: string): Calls PUT /api/folders/{folderId}, on success calls fetchFolders, handles loading/errors.  
  2. Add "Rename" trigger (e.g., context menu in FolderTreeNode). Needs folderId and current name.  
  3. Create src/components/folders/RenameFolderModal.tsx (or use inline edit). Props: isOpen, onClose, folderId, currentName.  
  4. Modal State: newName, isSaving, saveError. Pre-fill input with currentName.  
  5. handleSave: Call renameFolder action from folderStore. Handle loading/error state. Display saveError (esp. for 409 conflict). Close modal on success.  
  6. Connect components to use folderStore.  
  7. Style according to **KC-ORG-UX-1**.  
  8. Write unit tests (**KC-ORG-TEST-FE-1**) for modal/inline edit, mocking store actions, testing success and error handling (409).

**12\. Ticket: KC-ORG-FE-4: Implement Folder Deletion UI & Logic**

* **Prompt:** Implement the UI and logic for deleting folders with confirmation, using Zustand, as specified in **JIRA Ticket KC-ORG-FE-4**.  
  1. **Zustand Store (folderStore):**  
     * Action deleteFolder(folderId: string): Calls DELETE /api/folders/{folderId}, on success calls fetchFolders, handles loading/errors, potentially returns specific error message for 400 (not empty).  
  2. Add "Delete" trigger (e.g., context menu in FolderTreeNode). Needs folderId.  
  3. Use Chakra AlertDialog. Trigger onOpen from delete action.  
  4. Dialog State: isDeleting, deleteError.  
  5. Implement handleConfirmDelete: Call deleteFolder action from folderStore. Handle loading state. If action returns specific error (e.g., "Folder is not empty"), display it in toast/dialog. Close dialog on success or cancel. Refresh list via store.  
  6. Connect components to use folderStore.  
  7. Style according to **KC-ORG-UX-1**.  
  8. Write unit tests (**KC-ORG-TEST-FE-1**) for dialog and confirm logic, mocking store actions, testing success and specific 400 error handling.

**13\. Ticket: KC-ORG-FE-6: Implement Move Card to Folder UI Logic**

* **Prompt:** Implement the UI and logic for moving cards into folders, as specified in **JIRA Ticket KC-ORG-FE-6**. Choose **one** approach (DND or Menu).  
  1. **API Call Function:** Create a helper async function moveCard(cardId: string, folderId: string | null) that calls fetch(\\/api/cards/${cardId}\`, { method: 'PUT', ..., body: JSON.stringify({ folderId }) })\`, handles success (toast) and errors (toast).  
  2. **Option A (Drag and Drop):**  
     * Install DND library (e.g., @dnd-kit/core, @dnd-kit/sortable).  
     * Wrap card list (**KC-CARD-FE-6-BLOCK**) and folder tree (**KC-ORG-FE-1**) with DND context providers.  
     * Make card items draggable (useDraggable). Provide cardId.  
     * Make folder tree nodes droppable (useDroppable). Provide folderId (or null for a root drop target).  
     * Implement onDragEnd handler: Get cardId from active.id, folderId from over.id. Call moveCard(cardId, folderId). Handle visual feedback during drag.  
  3. **Option B ("Move to" Menu):**  
     * Add "Move to" Button or Menu to card items (in **KC-CARD-FE-6-BLOCK** or **KC-CARD-FE-3-BLOCK**). Needs cardId.  
     * On click, open a Modal or Menu displaying folder choices. This could reuse parts of FolderTree or be a simpler list fetched from folderStore. Include a "Root" option (value null).  
     * On selecting a folder/root, get the targetFolderId and call moveCard(cardId, targetFolderId).  
  4. Consider UI feedback (loading state on card/folder, success/error toasts). Refreshing card lists might be needed if filtering by folder is implemented later.  
  5. Write tests (**KC-ORG-TEST-FE-1**) for the chosen interaction: (DND) Mock DND handlers, test onDragEnd calls moveCard. (Menu) Test modal/menu interaction, test moveCard call on selection. Mock fetch.

**14\. Ticket: KC-ORG-TEST-BE-1: Write Unit Tests for Folder API Logic**

* **Prompt:** Write comprehensive unit/integration tests for the Folder and related Card Move API endpoints using Jest/Vitest as specified in **JIRA Ticket KC-ORG-TEST-BE-1**.  
  1. Create test files (e.g., tests/integration/api/folders/..., update tests/integration/api/cards/\[cardId\]/route.test.ts).  
  2. Mock prisma client, getCurrentUserId.  
  3. **GET /api/folders:** Test success (flat list), empty, auth.  
  4. **POST /api/folders:** Test success (root/nested), validation, parent ownership, name conflict (409), auth.  
  5. **PUT /api/folders/{folderId}:** Test success, validation, ownership, name conflict (409), auth.  
  6. **DELETE /api/folders/{folderId}:** Test success (empty), non-empty check (400), ownership, auth.  
  7. **PUT /api/cards/{cardId} (Move Logic):** Test moving to folder, moving to root (null), target folder ownership check (400), card ownership check (404), auth.  
  8. Follow testing practices, reset mocks.

**15\. Ticket: KC-ORG-TEST-FE-1: Write Unit Tests for Folder UI Components**

* **Prompt:** Write unit tests for the key Folder UI components using Jest and React Testing Library as specified in **JIRA Ticket KC-ORG-TEST-FE-1**.  
  1. Create test files alongside components.  
  2. Mock fetch, next/navigation, @chakra-ui/react, and **Zustand store (folderStore)**.  
  3. **FolderTree/Node:** Test rendering (mock store state), expand/collapse, tree building util.  
  4. **Create/Rename/Delete Modals/Interactions:** Test opening, form input, validation, calling mocked store actions (addFolder, renameFolder, deleteFolder), handling success/error from mocked actions.  
  5. **Move Card UI (DND or Menu):** Test interaction logic, calling fetch (for PUT card) correctly based on user action (drag end or menu selection). Mock DND hooks if needed.  
  6. Follow testing practices, use renderWithProviders. Mocking store state/actions is crucial.