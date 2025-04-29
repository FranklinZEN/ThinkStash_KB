# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- User Authentication (Epic KC-AUTH): Implemented user registration, login (email/password via NextAuth CredentialsProvider), session management (JWT), profile view/update APIs and pages.
- Knowledge Card CRUD (Epic KC-CARD-CREATE): Implemented creation, reading, updating, and deletion of knowledge cards.
- Rich Text Editing: Integrated BlockNote.js (`@blocknote/react` + `@blocknote/mantine`) for card content, storing content as JSON.
- Basic Tagging: Added schema and backend logic for many-to-many tagging of cards.
- Core backend/frontend testing setup (Jest).
- Foundational project setup (Next.js, Prisma, Chakra UI, Docker, Code Quality tools).

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Resolved issues with BlockNote editor initialization and `editable` state management on card detail/edit pages.
- Corrected BlockNote content loading logic in card detail page (`replaceBlocks` vs `tryParseMarkdownToBlocks`).
- Fixed BlockNote import issues (`useBlockNote` vs `BlockNoteView` sources).
- Ensured BlockNote editor is editable by default on the new card page.

### Security
- Implemented password hashing using bcryptjs. 