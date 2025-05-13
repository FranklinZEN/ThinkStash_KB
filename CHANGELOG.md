# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2024-03-21

### Added
- **Manual Keyword/Hashtag System (Core Functionality):**
  - Users can now add, edit, and remove keywords (treated as hashtags with a '#' prefix) on both the "Create New Card" and "Edit Card" pages.
    - Keywords are automatically prefixed with '#' if not already present upon entry.
    - UI displays keywords as styled "tags" with a 3D-like effect.
    - Font and color styling for the keyword input field and labels implemented as per requirements (Open Sans, specific point sizes, and colors).
  - The "Key Words" input section is now consistently positioned after "Title" and before "Content" on the "Create New Card" and "Edit Card" pages.
  - Backend API endpoints (`/api/cards` and `/api/cards/[cardId]`) now robustly handle the creation, update, and retrieval of these keywords/tags associated with knowledge cards.
  - Tags are displayed in the read-only view of a card.
- **Enhanced Form Navigation:**
  - Added "Cancel" buttons to the "Create New Card" form (redirects to homepage) and the "Edit Card" form (reverts local changes and exits edit mode).
- **Build & Type Fixes:**
  - Resolved various build errors and type inconsistencies, including:
    - `VStack not defined` error in `src/app/cards/[cardId]/page.tsx`.
    - `dynamic not defined` error in `src/app/cards/[cardId]/page.tsx`.
    - Corrected type definitions for `Tag` and `KnowledgeCard` interfaces in `src/app/cards/[cardId]/page.tsx` to align frontend expectations with API responses (handling `Tag` objects vs. `string[]`).
    - Resolved `PartialBlock not defined` error in `src/app/cards/new/page.tsx`.
    - Addressed linter warnings for unused variables.
- Card content preview now appears in a Popover on hover instead of a flip animation.
- Folders can now be created directly within the "Move Card to Folder" modal.
- API route created to handle moving cards (`PUT /api/cards/[cardId]/move`).
- Visual indicator (star icon) added to starred cards in the list.
- API endpoint created to toggle card star status (`PUT /api/cards/[cardId]/star`).
- API endpoint created to create folders (`POST /api/folders`).

### Changed
- Refined error handling and state management for card creation and editing pages.
- Improved consistency in how editor content is handled and saved.
- Card action menu is now triggered by a dedicated hamburger icon button, not clicking the card.
- "Move Card to Folder" modal now uses the central Zustand store (`useFolderStore`) to ensure the sidebar folder list updates upon folder creation.
- Folder deletion logic updated: Instead of blocking deletion of non-empty folders, cards within are now uncategorized (`folderId=null`) and sub-folders are promoted to the parent level before the folder is deleted. Confirmation dialog text updated to reflect this.
- Date formatting in `CardListItem` moved to `useEffect` to prevent hydration errors.
- Corrected `params` handling in `DELETE /api/folders/[folderId]` route to use `await params` before validation.

### Fixed
- Ensured keywords/tags are correctly saved and displayed after creation and updates.
- Addressed issues where new keywords were not showing up post-save.
- Corrected logic for `canSave` state in the edit card page to accurately reflect changes in keywords.
- Resolved React child errors related to rendering tag objects directly instead of their name property.
- Corrected prop name mismatch (`onConfirm` vs `onConfirmMove`) in `ChangeFolderModal`, resolving move card errors.
- Fixed star/unstar functionality API errors by correcting imports (`getCurrentUserId` -> `getServerSession`, `prisma` default -> named).
- Fixed folder creation error ("mutateFolders is not a function") by switching `ChangeFolderModal` to use the correct store action/refresh mechanism.
- Fixed card snippet generation for JSON content by adding `JSON.parse`.
- Fixed folder deletion API returning 400 error due to incorrect `params` type (Promise instead of object) by adding `await params`.

## [0.2.0] - 2024-03-20

### Added
- Initial project setup using Next.js 14 (App Router, TypeScript).
- Core backend dependencies installed (Prisma, NextAuth, pg, bcryptjs).
- Core frontend dependencies installed (Chakra UI, Emotion, Framer Motion, Zustand, Blocknote, React Flow).
- Basic Chakra UI provider and theme configuration.
- Initial `src/` directory structure.
- Basic `.gitignore`, `tsconfig.json`, `.env.example`.
- Initial Prisma schema with NextAuth models and basic application models (User, Account, Session, VerificationToken, Folder, KnowledgeCard, Tag).
- Initial database migration generated and applied.
- Basic reusable `Layout` component (`src/components/layout/Layout.tsx`) with placeholders, integrated into root layout.
- Basic NextAuth.js configuration (`src/lib/auth.ts`, `src/app/api/auth/[...nextauth]/route.ts`) with Prisma adapter, JWT strategy, and stub Credentials provider.
- Prisma client singleton (`src/lib/prisma.ts`).
- `.nvmrc` file specifying Node.js v18.17.0.
- Code quality tools setup (ESLint, Prettier, Husky pre-commit hook, lint-staged).
- `docker-compose.yml` for local PostgreSQL development database.
- Initial `README.md` with prerequisites and getting started instructions.
- Backend testing framework setup (Jest, `ts-jest`, separate config).

## [Unreleased]
### Added
- Successfully configured Google Cloud Build trigger for the Next.js backend (linked to `ThinkStash_KB_Fresh_Filter/cloudbuild.yaml`). The build now correctly sets up Node.js (using nvm) and installs npm dependencies, and uses `CLOUD_LOGGING_ONLY`.

[0.2.1]: https://github.com/FranklinZEN/ThinkStash_KB/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/FranklinZEN/ThinkStash_KB/releases/tag/v0.2.0 


- Proceed a test for Google CI/CD