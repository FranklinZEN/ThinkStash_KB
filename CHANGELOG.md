# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased] - YYYY-MM-DD

### Added
- Card content preview now appears in a Popover on hover instead of a flip animation.
- Folders can now be created directly within the "Move Card to Folder" modal.
- API route created to handle moving cards (`PUT /api/cards/[cardId]/move`).
- Visual indicator (star icon) added to starred cards in the list.
- API endpoint created to toggle card star status (`PUT /api/cards/[cardId]/star`).
- API endpoint created to create folders (`POST /api/folders`).

### Changed
- Card action menu is now triggered by a dedicated hamburger icon button, not clicking the card.
- "Move Card to Folder" modal now uses the central Zustand store (`useFolderStore`) to ensure the sidebar folder list updates upon folder creation.
- Folder deletion logic updated: Instead of blocking deletion of non-empty folders, cards within are now uncategorized (`folderId=null`) and sub-folders are promoted to the parent level before the folder is deleted. Confirmation dialog text updated to reflect this.
- Date formatting in `CardListItem` moved to `useEffect` to prevent hydration errors.
- Corrected `params` handling in `DELETE /api/folders/[folderId]` route to use `await params` before validation.

### Fixed
- Corrected prop name mismatch (`onConfirm` vs `onConfirmMove`) in `ChangeFolderModal`, resolving move card errors.
- Fixed star/unstar functionality API errors by correcting imports (`getCurrentUserId` -> `getServerSession`, `prisma` default -> named).
- Fixed folder creation error ("mutateFolders is not a function") by switching `ChangeFolderModal` to use the correct store action/refresh mechanism.
- Fixed card snippet generation for JSON content by adding `JSON.parse`.
- Fixed folder deletion API returning 400 error due to incorrect `params` type (Promise instead of object) by adding `await params`.

## [Unreleased]

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

[Unreleased]: https://github.com/your-username/knowledge-card-system/compare/HEAD 