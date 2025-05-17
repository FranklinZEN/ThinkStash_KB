# Project Progress Tracker

## Epic 1: KC-SETUP - Initial Project Setup

- [x] KC-SETUP-1: Initialize Next.js Project with TypeScript
- [x] KC-SETUP-2: Install Core Backend Dependencies (PostgreSQL Focus) *(Partially completed: `.env` created, dependencies installed, Prisma initialized. Manual `NEXTAUTH_SECRET` needed)*
- [x] KC-SETUP-3: Install Core Frontend Dependencies *(Chakra, Emotion, Framer, Zustand, Blocknote, React Flow installed & configured)*
- [x] KC-SETUP-4: Define Basic Project Structure *(Partially completed: Core `src/` dirs created. README update pending)*
- [x] KC-SETUP-5: Define Initial Prisma Schema Models
- [x] KC-SETUP-6: Implement Basic Layout Component
- [x] KC-SETUP-7: Configure NextAuth.js Options
- [x] KC-SETUP-8: Implement Prisma Client Singleton
- [x] KC-SETUP-9: Add .nvmrc File
- [x] KC-70: Setup Code Quality Tools
- [x] KC-71: Create Docker Compose for Local Development DB
- [x] KC-74: Create Initial Project README
- [ ] KC-TEST-FE-1: Setup Frontend Unit Testing Framework *(Setup complete, but test execution fails with module resolution error - needs revisit)*
- [x] KC-TEST-BE-1: Setup Backend Unit/Integration Testing Framework

**Overall Phase A (Local MVP Enhancement) Summary:**
- [x] **KC-OPTIMIZE-S1 - Pre-Stage 2 Code & Performance Optimization:** Completed profiling and optimization efforts across backend, database, and frontend for the local MVP.
- [x] **KC-UXUI-ENHANCE-S1-LOCAL - Comprehensive UI/UX Design & Local Enhancement:** Completed comprehensive Figma designs and aligned existing Stage 1 components with these designs, including Chakra UI custom theme updates.

## Feature Development (Epics 3, 4, 4.5)

This summarizes the major feature work completed after initial setup.

**Core Card Functionality (Epic 3 & Revisions):**
- [x] Knowledge Card Creation/Editing using BlockNote editor.
- [x] Card list display API (`GET /api/cards`) and basic UI.
- [x] Card delete functionality (frontend confirmation + `DELETE /api/cards/[cardId]` API).

**Folder Management & Organization (Epic 4 & Revisions):**
- [x] Folder creation API (`POST /api/folders`) and basic UI structure.
- [x] Folder renaming API (`PUT /api/folders/[folderId]`) and modal.
- [x] Folder deletion API (`DELETE /api/folders/[folderId]`) updated to handle moving contents instead of blocking on non-empty folders.
- [x] Sidebar folder tree display using Zustand (`useFolderStore`).
- [x] Folder creation integrated into "Move Card" modal, updating the store/sidebar.

**Card Interaction & Display Refinements (Epic 4.5):**
- [x] Card List Item UI:
    - Displays folder name.
    - Displays latest activity date (created/updated), handling hydration issues.
    - Displays content snippet preview in a Popover on hover (replaced flip animation).
    - Includes action menu triggered by Hamburger icon.
- [x] Card Action Menu:
    - Provides View/Edit, Delete, Move to Folder, Star/Unstar options.
- [x] Move Card Functionality:
    - "Move to Folder" modal implemented.
    - API route `PUT /api/cards/[cardId]/move` created and functional.
- [x] Starred Card Functionality:
    - `isStarred` field added to `KnowledgeCard` model.
    *   API route `PUT /api/cards/[cardId]/star` created and functional.
    *   Star indicator icon added to card list items.
    *   API sorts starred cards first (frontend relies on this order).

**Key Fixes:**
- [x] Resolved various API route errors (imports, missing routes, `await params` issue).
- [x] Fixed state synchronization issues between modals and sidebar (`useFolderStore`).
- [x] Resolved card snippet generation/parsing issues for JSON content.
- [x] Fixed frontend hydration errors related to date formatting.

**Next Steps / Areas for Testing:**
- [ ] Subfolder creation via sidebar/tree node menu.
- [ ] Folder renaming thorough testing.
- [ ] Deleting folders containing subfolders (verify promotion logic).
- [ ] Starred card sorting verification in UI.
- [ ] Folder drag-and-drop reordering testing (if implemented).
- [ ] Edge case testing (duplicate names, deep nesting, errors, touch devices).
- [ ] Accessibility review.
- [ ] Add confirmation dialog for moving cards (currently deferred). 

**Tagging & Keyword Management (Manual Hashtag System):**
- [x] Manual keyword/hashtag input implemented for "Create New Card" page.
- [x] Manual keyword/hashtag editing (add, remove, view) implemented for "Edit Card" page.
- [x] Keywords automatically prefixed with '#' to function as hashtags.
- [x] UI styling for keyword input field, labels, and displayed tags (Open Sans font, specified sizes, colors, 3D-like effect).
- [x] "Key Words" section consistently positioned between "Title" and "Content" on create/edit forms.
- [x] Backend API support for creating, updating, and retrieving tags/keywords with cards.
- [x] Tags/keywords are displayed in the read-only view of a card.
- [x] Ensured keywords/tags are correctly saved and displayed post-creation/update.
- [x] Corrected logic for `canSave` button state to accurately reflect keyword changes on edit page.

**Form Navigation & UX Enhancements:**
- [x] "Cancel" button added to "Create New Card" form (navigates to homepage).
- [x] "Cancel" button added to "Edit Card" form (reverts local changes, exits edit mode).
- [x] Addressed various linter warnings for unused variables.
- [x] Fixed React child errors from rendering tag objects instead of `tag.name`.

**Build & Type System Fixes (Related & General):**
- [x] Resolved `VStack not defined` error in card detail page.
- [x] Resolved `dynamic not defined` error in card detail page.
- [x] Corrected `Tag` and `KnowledgeCard` type definitions to align frontend with API (object tags vs. string arrays).
- [x] Resolved `PartialBlock not defined` error in new card page.

## Infrastructure Milestones
- [x] **EPIC: KC-GCP-INFRA - GCP Foundation & Deployment:** Successfully provisioned core GCP infrastructure including Terraform setup, Cloud SQL (PostgreSQL with pgvector), Cloud Storage, Memorystore for Redis, IAM roles, Secret Manager, and foundational monitoring.

### Epic 5: KC-CICD-GCP - CI/CD Pipeline on Google Cloud (Part of KC-GCP-INFRA)
- [x] KC-CICD-1: Define `cloudbuild.yaml` for build, test, Docker image creation, and push to Artifact Registry.
- [x] KC-CICD-2: Implement database migration step in `cloudbuild.yaml` using Cloud SQL Proxy for PostgreSQL.
- [x] KC-CICD-3: Implement deployment to Cloud Run step in `cloudbuild.yaml`.
- [x] KC-CICD-4: Configure Cloud Build trigger for automated builds on push to main branch.
- [x] KC-CICD-5: Securely manage database credentials using Secret Manager and `availableSecrets`.
- [x] KC-CICD-6: Iteratively debug and stabilize the entire CI/CD pipeline (Phases 1-Final). 