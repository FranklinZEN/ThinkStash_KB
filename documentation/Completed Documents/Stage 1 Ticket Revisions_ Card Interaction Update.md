## **Stage 1 Ticket Revisions: Card Interaction Update**

This document outlines the necessary revisions and additions to Stage 1 tickets to implement the updated card interaction model: Hover-to-flip preview, Click-for-actions menu (replacing card DND move), and Starred card functionality.

### **Existing Ticket Revisions**

**1\. Ticket Revision: KC-ORG-FE-6 (Implement Move Card to Folder UI Logic)**

* **Original Goal:** Implement UI for moving cards (DND or Menu).  
* **New Goal:** Remove DND logic for moving cards. Retain the underlying handleMoveCard function (which calls the API) to be triggered by the new Action Menu (KC-CARD-FE-10).  
* **Revised Technical Approach (AI-Friendly Prompt):**  
  1. Remove any installed Drag-and-Drop libraries (react-beautiful-dnd, @dnd-kit/core) if they were *only* used for moving cards between folders (keep if used for moving folders themselves in KC-ORG-FE-7).  
  2. Remove useDraggable hooks and associated props/event handlers from the card list item component (DraggableCardItem or similar).  
  3. Remove useDroppable hooks and associated logic from the folder tree nodes (FolderTreeNode) related to accepting cards.  
  4. Remove the onDragEnd handler logic related to card-to-folder drops from the main layout or DND context provider (Layout.tsx).  
  5. **Retain/Refactor:** Keep the core handleMoveCard(cardId, folderId) function (likely defined in Layout.tsx or moved to a store/utility) that contains the fetch call to PUT /api/cards/{cardId} with the folderId. This function will now be invoked by the "Change Folder" modal initiated from the revised KC-CARD-FE-10 action menu. Ensure it handles loading states and displays toasts appropriately.  
* **Dependencies:** Now primarily depends on KC-CARD-FE-10 triggering the move action.
* **Status Note:** Move action is triggered via a modal from the card menu. `ChangeFolderModal` implemented and API route `PUT /api/cards/[cardId]/move/route.ts` created and fixed. Prop mismatch resolved.

**2\. Ticket Revision: KC-CARD-FE-9 (Implement Card Flip Animation for Content Preview)**

* **Original Goal:** Flip card onClick to show snippet.  
* **New Goal:** Flip card onMouseEnter/onMouseLeave (hover) to show snippet.  
* **Revised Technical Approach (AI-Friendly Prompt):**  
  1. **Trigger Change:** In the card list item component (CardListItem.tsx or similar), remove the onClick={handleFlip} handler from the main card container (flip-card).  
  2. Add onMouseEnter={handleMouseEnter} and onMouseLeave={handleMouseLeave} handlers to the main card container.  
  3. Implement handleMouseEnter \= () \=\> setIsFlipped(true);  
  4. Implement handleMouseLeave \= () \=\> setIsFlipped(false);  
  5. **Keep:** Retain the isFlipped state, the CSS classes and styles for the flip animation, the component structure (flip-card, flip-card-inner, etc.), and the logic for displaying the snippet (extractSnippetFromContent) on the back face.  
  6. Ensure hover events work correctly on touch devices (may require alternative handling or disabling flip on touch). Consider adding a slight delay before flipping on hover using setTimeout/clearTimeout to prevent flickering when moving the mouse quickly over cards.  
* **Dependencies:** No change in dependencies.
* **Status Note:** Implementation deviated. Flip animation proved problematic. Replaced with a hover-triggered `Popover` component displaying the snippet. Snippet generation fixed for JSON content. Hydration errors resolved.

**3\. Ticket Revision: KC-CARD-FE-10 (Implement Card Action Menu)**

* **Original Goal:** Action menu triggered by ellipsis button. Options: Edit, Delete, Change Folder.  
* **New Goal:** Action menu triggered by *clicking the main card area*. Options: View/Edit, Delete, Change Folder, Star/Unstar.  
* **Revised Technical Approach (AI-Friendly Prompt):**  
  1. **Trigger Change:** Remove the ellipsis IconButton and the wrapping Chakra UI Menu trigger from the card list item component (CardListItem.tsx).  
  2. **New Trigger:** Add an onClick handler to the main card container (the same one handling hover for flip, but ensure click doesn't interfere with hover state if flip is mid-animation). This onClick handler should open a context menu or a modal presenting the actions. Using a **Modal** might be simpler given the required "Change Folder" sub-flow.  
  3. **Implement Action Modal:**  
     * Create state to manage the modal's visibility and the selectedCard data: const \[actionModalOpen, setActionModalOpen\] \= useState(false); const \[selectedCard, setSelectedCard\] \= useState\<CardListItem | null\>(null);  
     * The card container's onClick handler should do: setSelectedCard(card); setActionModalOpen(true);.  
     * Create an ActionModal component using Chakra UI Modal. Pass isOpen={actionModalOpen}, onClose={() \=\> setActionModalOpen(false)}, and card={selectedCard} as props.  
     * Inside ActionModal:  
       * Display the Card Title.  
       * Provide buttons or links for actions:  
         * **"View/Edit":** Button/Link using router.push(\\/cards/${card.id}/edit\`)\`.  
         * **"Delete":** Button that triggers the existing delete confirmation flow (KC-ORG-FE-9/KC-CARD-FE-5-BLOCK). Pass the card.id and potentially onClose of the action modal to the delete flow.  
         * **"Change Folder":** Button that opens *another* modal (ChangeFolderModal \- see original KC-CARD-FE-10 description) allowing folder selection and calling handleMoveCard. Pass card.id and onClose of the action modal.  
         * **"Star/Unstar":** Button that calls a new handler handleToggleStar(card.id, card.isStarred) (defined in KC-STAR-FE-1). Display text dynamically ("Star" or "Unstar") based on card.isStarred status (requires KC-STAR-BE-1/KC-STAR-FE-2).  
       * Ensure the modal closes after an action is completed or cancelled.  
* **Dependencies:** Add dependency on KC-STAR-FE-1 (Star action handler/state) and KC-STAR-FE-2 (Starred status data).
* **Status Note:** Implementation deviated slightly. Menu is triggered by a dedicated `HamburgerIcon` `MenuButton` positioned on the card, not the main card area click. `ChangeFolderModal` implemented with folder creation added. Star/Unstar button functional.

**4\. Ticket Revision: KC-ORG-FE-9 (Implement Confirmation Dialog for Moving Cards)**

* **Original Goal:** Confirmation dialog triggered by DND drop.  
* **New Goal:** Confirmation dialog triggered by confirming selection in the "Change Folder" modal launched from the main card action menu (KC-CARD-FE-10).  
* **Revised Technical Approach (AI-Friendly Prompt):**  
  1. The core AlertDialog component and its logic for displaying messages based on currentFolderId/targetFolderId remain largely the same.  
  2. Instead of being triggered directly within a DND handler, the onOpen for this confirmation dialog should be called from the "Save" button handler within the ChangeFolderModal (created as part of the revised KC-CARD-FE-10), *after* a target folder has been selected but *before* the API call (handleMoveCard) is made.  
  3. Pass the necessary context (cardId, cardTitle, currentFolderId, currentFolderName, targetFolderId, targetFolderName) from the ChangeFolderModal to the AlertDialog when opening it.  
  4. The "Confirm" button within the AlertDialog remains responsible for finally calling the handleMoveCard API function.  
* **Dependencies:** Now triggered by the modal flow in revised KC-CARD-FE-10. Still depends on KC-ORG-FE-10 for folder data.
* **Status Note:** Currently, no separate confirmation dialog exists. The `ChangeFolderModal` directly calls the move API upon clicking a folder button. This might need revisiting if explicit confirmation is desired.

### **New Tickets for "Starred" Functionality**

Ticket ID: KC-STAR-BE-1  
Title: Update Card Schema and API for Starred Status  
Epic: KC-CARD-CREATE / KC-ORG  
PRD Requirement(s): Implied Usability Enhancement  
Team: BE  
Dependencies (Functional): KC-20.1-BLOCK (Card Schema), KC-8.2 (Auth Check)  
UX/UI Design Link: N/A  
Description (Functional): Add a 'starred' flag to cards and provide an API endpoint to toggle this status. Modify the card list API to include starred status and sort starred items first.  
Acceptance Criteria (Functional):

* Card model in Prisma schema includes an optional boolean field isStarred (defaulting to false or null).  
* A PUT or PATCH endpoint exists (e.g., PUT /api/cards/{cardId}/star) that toggles the isStarred value for a specific card owned by the user.  
* The endpoint returns the updated starred status or the updated card.  
* The main card list endpoint (GET /api/cards) includes the isStarred field in its response.  
* The GET /api/cards endpoint sorts results so that starred cards (isStarred: true) appear before unstarred cards, potentially as a secondary sort after a primary sort like updatedAt.  
* Standard ownership checks and error handling apply.  
  Technical Approach / Implementation Notes (AI-Friendly Prompt):  
1. **Schema Change (KC-20.1-BLOCK Revision):**  
   * Add isStarred Boolean? @default(false) to the Card model in prisma/schema.prisma.  
   * Add @@index(\[userId, isStarred\]) to potentially optimize fetching starred cards.  
   * Run npx prisma migrate dev \--name add-card-starred-status. Run npx prisma generate.  
2. **Toggle Star API:**  
   * Create app/api/cards/\[cardId\]/star/route.ts. Export async function PUT(request: Request, { params }).  
   * Import NextResponse, prisma, getCurrentUserId. Validate params.cardId. Auth check (userId).  
   * Fetch the current card to check ownership and current star status: const card \= await prisma.card.findUnique({ where: { id: params.cardId, userId } }); if (\!card) { /\* 404 \*/ }.  
   * Toggle the status: const newStarredStatus \= \!card.isStarred;.  
   * Update the card: const updatedCard \= await prisma.card.update({ where: { id: params.cardId }, data: { isStarred: newStarredStatus }, select: { id: true, isStarred: true } });.  
   * Return NextResponse.json(updatedCard);. Handle errors.  
3. **List API Revision (KC-CARD-BE-4-BLOCK Revision):**  
   * Modify the GET /api/cards handler (app/api/cards/route.ts).  
   * Add isStarred: true to the select clause in prisma.card.findMany.  
   * Modify the orderBy clause to sort by starred status first, then by another criteria (e.g., updatedAt): orderBy: \[{ isStarred: 'desc' }, { updatedAt: 'desc' }\]. (desc puts true before false/null).  
     API Contract (if applicable): Adds PUT /api/cards/{cardId}/star. Modifies response of GET /api/cards (adds isStarred, changes sort order).  
     Data Model Changes (if applicable): Adds isStarred field to Card table.  
     Key Functions/Modules Involved: prisma/schema.prisma, new API route handler, existing GET /api/cards handler, Prisma Client.  
     Testing Considerations (Technical): Test schema migration. Test toggle API success, ownership check, errors. Test list API includes isStarred and correctly sorts starred items first.  
     Dependencies (Technical): KC-20.1-BLOCK, KC-8.2, KC-CARD-BE-4-BLOCK.
* **Status Note:** Implemented. Schema updated, toggle API (`PUT /api/cards/[cardId]/star`) created and fixed, list API modifications assumed done (needs verification if list sorting isn't working).

Ticket ID: KC-STAR-FE-1  
Title: Implement Star/Unstar Action in Card Menu  
Epic: KC-CARD-CREATE / KC-ORG  
PRD Requirement(s): Implied Usability Enhancement  
Team: FE  
Dependencies (Functional): KC-STAR-BE-1 (Toggle API), KC-CARD-FE-10 (Revised Action Menu)  
UX/UI Design Link: N/A (Uses existing menu structure)  
Description (Functional): Implement the client-side logic to call the toggle star API when the user clicks the "Star/Unstar" option in the card action menu.  
Acceptance Criteria (Functional):

* The "Star/Unstar" button in the action modal (KC-CARD-FE-10) correctly displays "Star" if the card is not starred, and "Unstar" if it is.  
* Clicking the button calls the PUT /api/cards/{cardId}/star endpoint.  
* Loading state is indicated during the API call.  
* On success, the UI optimistically updates the star status (or refetches data) and shows a confirmation toast.  
* Errors are handled with a toast message.  
  Technical Approach / Implementation Notes (AI-Friendly Prompt):  
1. **Modify Action Modal (KC-CARD-FE-10):**  
   * Ensure the modal receives the full card object, including the isStarred status (requires KC-STAR-BE-1 changes to GET /api/cards and corresponding FE state updates).  
   * Dynamically set the text of the Star/Unstar button: {card.isStarred ? 'Unstar' : 'Star'}.  
   * Add useState for loading state: const \[isStarring, setIsStarring\] \= useState(false);.  
   * Implement the handleToggleStar function:  
     const handleToggleStar \= async (cardId: string, currentStatus: boolean | null | undefined) \=\> {  
       setIsStarring(true);  
       try {  
         const response \= await fetch(\`/api/cards/${cardId}/star\`, { method: 'PUT' });  
         if (\!response.ok) throw new Error('Failed to toggle star');  
         const updatedCard \= await response.json();  
         // TODO: Update card state locally/in store (optimistic or refetch)  
         // e.g., call cardStore.updateCardStarStatus(cardId, updatedCard.isStarred);  
         toast({ title: \`Card ${updatedCard.isStarred ? 'starred' : 'unstarred'}\`, status: 'success' });  
         onClose(); // Close the action modal  
       } catch (error) {  
         toast({ title: 'Error', description: 'Could not update star status.', status: 'error' });  
       } finally {  
         setIsStarring(false);  
       }  
     };

   * Attach this handler to the Star/Unstar button's onClick, passing card.id and card.isStarred. Disable the button when isStarring.  
2. State Update: Implement the logic to update the card's star status in the frontend state (e.g., in the Zustand cardStore) after a successful API call to ensure the UI reflects the change immediately and the list resorts correctly on next fetch.  
   API Contract (if applicable): Consumes PUT /api/cards/{cardId}/star.  
   Data Model Changes (if applicable): N/A  
   Key Functions/Modules Involved: Action Modal component, handleToggleStar function, fetch, useState, useToast, state management update logic (e.g., Zustand store action).  
   Testing Considerations (Technical): Unit test handleToggleStar (mock fetch, toast, state update). E2E test clicking Star/Unstar action, verify API call, toast message, and subsequent UI update (star indicator, list order).  
   Dependencies (Technical): KC-STAR-BE-1, KC-CARD-FE-10 (Revised).
* **Status Note:** Implemented. Star/Unstar button added to card menu (via `CardListItem`), `handleToggleStar` implemented, API is called.

Ticket ID: KC-STAR-FE-2  
Title: Add Visual Indicator for Starred Cards  
Epic: KC-CARD-CREATE / KC-ORG  
PRD Requirement(s): Implied Usability Enhancement  
Team: FE  
Dependencies (Functional): KC-STAR-BE-1 (API provides status), KC-CARD-FE-6-BLOCK (Card List UI)  
UX/UI Design Link: \[Link to Figma/mockups for Starred Indicator\] (Requires UX input)  
Description (Functional): Display a visual indicator (e.g., a star icon) on card items in the list view to clearly show which cards have been marked as starred by the user.  
Acceptance Criteria (Functional):

* Card list items (CardListItem.tsx or similar) display a distinct visual indicator (e.g., a filled star icon) if the card's isStarred property is true.  
* The indicator is not displayed if isStarred is false or null/undefined.  
* The indicator is placed appropriately according to UX design (e.g., near the title, corner).  
  Technical Approach / Implementation Notes (AI-Friendly Prompt):  
1. **Modify Card List Item Component (CardListItem.tsx):**  
   * Ensure the component receives the card object including the isStarred boolean property (requires KC-STAR-BE-1 changes to GET /api/cards and corresponding FE state updates).  
   * Conditionally render a star icon based on card.isStarred.  
   * Use an appropriate icon library (e.g., react-icons/bs for BsStarFill or BsStar) or Chakra UI's Icon.  
   * Example:  
     // Inside the CardListItem component, e.g., near the title  
     {card.isStarred && (  
       \<Icon as={BsStarFill} color="yellow.400" ml={2} aria-label="Starred" /\>  
     )}

   * Position the icon according to UX design using Chakra layout props (position, top, right, or within a Flex container).  
     API Contract (if applicable): Relies on GET /api/cards providing isStarred field.  
     Data Model Changes (if applicable): N/A  
     Key Functions/Modules Involved: Frontend card list item component, Chakra UI Icon or icon library, conditional rendering logic.  
     Testing Considerations (Technical): Unit test the component to verify the star icon renders conditionally based on the isStarred prop. E2E test the card list to ensure starred cards are visually distinct.  
     Dependencies (Technical): KC-STAR-BE-1, KC-CARD-FE-6-BLOCK.
* **Status Note:** Implemented. Star icon conditionally rendered on `CardListItem`.

Ticket ID: KC-STAR-FE-3  
Title: Ensure Starred Cards Appear First in List  
Epic: KC-CARD-CREATE / KC-ORG  
PRD Requirement(s): Implied Usability Enhancement  
Team: FE  
Dependencies (Functional): KC-STAR-BE-1 (API sorts correctly), KC-CARD-FE-6-BLOCK (Card List UI)  
UX/UI Design Link: N/A  
Description (Functional): Ensure the frontend card list view respects the sorting order provided by the backend API, displaying starred cards before non-starred cards.  
Acceptance Criteria (Functional):

* When the card list is fetched from GET /api/cards, the frontend renders the cards in the order received, which should have starred items first.  
* No additional client-side sorting based on isStarred is required if the API handles it correctly.  
  Technical Approach / Implementation Notes (AI-Friendly Prompt):  
1. **Verify API Sorting:** Confirm through testing or code review that the GET /api/cards endpoint (modified in KC-STAR-BE-1) correctly applies the orderBy: \[{ isStarred: 'desc' }, { updatedAt: 'desc' }\] clause.  
2. **Frontend Rendering:** Ensure the frontend card list component (KC-CARD-FE-6-BLOCK) simply maps over the array of cards received from the API (or state store) in the order it's provided. Avoid applying any client-side sorting that would override the intended starred-first order.  
   // In the component rendering the list (e.g., dashboard page)  
   // Assuming 'cards' state holds the array fetched from the API  
   {cards.map(card \=\> (  
     \<CardListItem key={card.id} card={card} /\>  
     // No client-side sort here based on isStarred  
   ))}

API Contract (if applicable): Relies on GET /api/cards providing correctly sorted data.  
Data Model Changes (if applicable): N/A  
Key Functions/Modules Involved: Frontend card list rendering component.  
Testing Considerations (Technical): E2E test the card list view with a mix of starred and unstarred cards. Verify that starred cards consistently appear at the top of the list (respecting the secondary sort order, e.g., updatedAt, among starred items).  
Dependencies (Technical): KC-STAR-BE-1, KC-CARD-FE-6-BLOCK.
* **Status Note:** Assumed working via backend API sorting. Needs verification in UI testing.