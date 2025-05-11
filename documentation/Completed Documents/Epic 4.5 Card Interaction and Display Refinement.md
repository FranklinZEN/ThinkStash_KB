# Epic 4.5: Card Interaction and Display Refinement

**Status**: [Implemented - with deviations noted]

*This document reflects the implemented state of card display, interaction, and starring features, combining and updating goals from previous Epic 4 definitions and Stage 1 revisions.*

## Card Display & Preview

**Ticket: Display Folder Name on Card List Items** (From Epic 4 Display Enhancement)
*   **Status**: [Implemented]
*   **Description**: Displays the name of the folder the card belongs to on the card list item.
*   **Implementation:** Done via `CardListItem.tsx`.

**Ticket: Implement Utility to Extract Text Snippet** (From Epic 4 Display Enhancement)
*   **Status**: [Implemented]
*   **Description**: Utility function `extractSnippetFromContent` created in `src/lib/cardUtils.ts` to get plain text from BlockNote JSON for previews.
*   **Implementation:** Function created and handles JSON parsing.

**Ticket: Implement Card Content Preview on Hover** (Revised KC-CARD-FE-9)
*   **Status**: [Implemented - Deviated from Flip]
*   **Description**: Shows a preview of the card's content when the user hovers over the card list item.
*   **Implementation Details**:
    *   Original flip animation was replaced with a Chakra UI `Popover` component due to implementation difficulties.
    *   Popover appears on hover after a short delay.
    *   `PopoverBody` displays the extracted snippet, with controlled max height (600px) and scrolling.
    *   Snippet generation handles JSON content and hydration errors were resolved.

## Card Actions Menu

**Ticket: Implement Card Action Menu** (Revised KC-CARD-FE-10)
*   **Status**: [Implemented - Deviated Trigger]
*   **Description**: Provides an action menu on each card for View/Edit, Delete, Change Folder, and Star/Unstar actions.
*   **Implementation Details**:
    *   Menu is triggered by a dedicated `HamburgerIcon` `MenuButton` positioned absolutely on the top-right of the card, not by clicking the main card area as originally revised.
    *   Menu includes options for View/Edit, Delete, Move to Folder, and Star/Unstar.
    *   "Move to Folder" opens `ChangeFolderModal`.

**Ticket: Implement "Move Card to Folder" Modal & Logic** (Revised KC-ORG-FE-6 & KC-CARD-FE-10)
*   **Status**: [Implemented]
*   **Description**: Provides a modal accessible from the card action menu to move a card to a different folder (or root) and allows creating new root folders.
*   **Implementation Details**:
    *   `ChangeFolderModal.tsx` created.
    *   Lists existing folders fetched via `useFolderStore`.
    *   Allows selecting an existing folder or "Root (No Folder)" to move the card.
    *   Includes an input and button to create a new root folder (`POST /api/folders`).
    *   Uses `useFolderStore` and its `addFolder` action to ensure folder list updates correctly across the app (including sidebar).
    *   Calls the `PUT /api/cards/[cardId]/move` API route to perform the move.
    *   Prop name mismatches and store update logic fixed.

**Ticket: Implement Move Card API Route** (Implied by KC-ORG-FE-6 Revision)
*   **Status**: [Implemented]
*   **Description**: Backend API endpoint to handle changing a card's `folderId`.
*   **Implementation Details**:
    *   Created `src/app/api/cards/[cardId]/move/route.ts`.
    *   Handles `PUT` requests.
    *   Validates user ownership of the card and the target folder (if not null).
    *   Updates `folderId` in the database.

**Ticket: Confirmation Dialog for Moving Cards** (Revised KC-ORG-FE-9)
*   **Status**: [Not Implemented/Deferred]
*   **Description**: Original plan was to show a confirmation dialog before moving a card.
*   **Implementation Details**: Currently, clicking a folder name in the `ChangeFolderModal` triggers the move API call directly without an extra confirmation step. This might be revisited.

## Starred Card Functionality

**Ticket: Update Card Schema and API for Starred Status** (KC-STAR-BE-1)
*   **Status**: [Implemented]
*   **Description**: Add `isStarred` field to cards and API endpoints to manage/view it.
*   **Implementation Details**:
    *   `isStarred: Boolean @default(false)` added to `KnowledgeCard` model in `schema.prisma`. Index added.
    *   `PUT /api/cards/[cardId]/star` route created to toggle status.
    *   `GET /api/cards` route modified to include `isStarred` and sort by `{ isStarred: 'desc' }` then `{ updatedAt: 'desc' }`.

**Ticket: Implement Star/Unstar Action in Card Menu** (KC-STAR-FE-1)
*   **Status**: [Implemented]
*   **Description**: Client-side logic to call the toggle star API from the card menu.
*   **Implementation Details**:
    *   Button added to `MenuList` in `CardListItem.tsx`.
    *   `handleToggleStar` function implemented, calls API, shows toasts.
    *   UI updates based on `isStarred` state within `CardListItem`.

**Ticket: Add Visual Indicator for Starred Cards** (KC-STAR-FE-2)
*   **Status**: [Implemented]
*   **Description**: Display a star icon on starred cards.
*   **Implementation Details**:
    *   `CardListItem.tsx` conditionally renders a `StarIcon` based on `card.isStarred`.
    *   Icon is positioned absolutely in the top-right corner.

**Ticket: Ensure Starred Cards Appear First in List** (KC-STAR-FE-3)
*   **Status**: [Implemented (Backend)]
*   **Description**: Ensure starred cards are sorted first in the list view.
*   **Implementation Details**: Handled by the `orderBy` clause in the `GET /api/cards` backend route. Frontend simply renders the received order. Verification needed during testing.

## Folder Deletion Enhancement

**Ticket: Modify Folder Deletion Logic** (Implicit Revision)
*   **Status**: [Implemented]
*   **Description**: Change folder deletion to allow deleting non-empty folders by handling contained items gracefully.
*   **Implementation Details**:
    *   `DELETE /api/folders/[folderId]` route updated.
    *   Removed check blocking deletion of non-empty folders.
    *   Uses `prisma.$transaction` to:
        *   Set `folderId = null` for cards within the folder.
        *   Set `parentId` of direct subfolders to the deleted folder's `parentId`.
        *   Delete the target folder.
    *   Frontend confirmation dialog text in `FolderTreeNode.tsx` updated to match this behavior.
    *   Fixed `await params` issue in the API route. 