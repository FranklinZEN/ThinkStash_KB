## **JIRA Epic: KC-SETUP \- Project Setup & Foundation (PostgreSQL Version)**

**Rationale:** Establish the core project structure, dependencies, and development environment standards necessary for collaborative development using PostgreSQL.

Ticket ID: KC-SETUP-1  
Title: Initialize Next.js Project with TypeScript  
Epic: KC-SETUP  
PRD Requirement(s): TC-STACK-1  
Team: BE  
Dependencies (Functional): None  
UX/UI Design Link: N/A  
Description (Functional): Set up the basic Next.js application framework using the standard tools to provide the foundation for development.  
Acceptance Criteria (Functional):

* The project can be cloned and installed successfully.  
* The basic application runs locally using the standard dev command.  
* The project uses TypeScript and the App Router structure.  
  Technical Approach / Implementation Notes:  
* Use npx create-next-app@latest . (or specify project name) with options: TypeScript: Yes, ESLint: Yes, Tailwind CSS: No (using Chakra UI), src/ directory: Yes, App Router: Yes.  
* Initialize Git repository: git init && git add . && git commit \-m "Initial commit".  
* Configure basic .gitignore (include .env, node\_modules, build outputs like .next, OS files, potentially docker-data/).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Project root files (package.json, tsconfig.json, next.config.js, .gitignore).  
* src/app directory structure (layout.tsx, page.tsx).  
  Testing Considerations (Technical): Verify default page loads with npm run dev.  
  Dependencies (Technical): Node.js v18+, npm/yarn installed.

Ticket ID: KC-SETUP-2  
Title: Install Core Backend Dependencies (PostgreSQL Focus)  
Epic: KC-SETUP  
PRD Requirement(s): TC-STACK-2, TC-STACK-3, TC-STACK-4  
Team: BE  
Dependencies (Functional): KC-SETUP-1  
UX/UI Design Link: N/A  
Description (Functional): Add the necessary backend libraries for database interaction (Prisma with PostgreSQL), authentication (NextAuth), and password security (bcryptjs) to the project.  
Acceptance Criteria (Functional):

* Required libraries (next-auth, @prisma/client, bcryptjs) are listed in package.json.  
* Project dependencies install without errors (npm install).  
* Prisma can be initialized successfully for PostgreSQL (npx prisma init).  
* Environment variables for PostgreSQL connection are defined.  
  Technical Approach / Implementation Notes:  
* Run npm install next-auth @prisma/client bcryptjs pg. (Add pg driver for PostgreSQL).  
* Run npm install \-D prisma @types/bcryptjs.  
* Run npx prisma init \--datasource-provider postgresql.  
* Update prisma/schema.prisma datasource block:  
  datasource db {  
    provider \= "postgresql"  
    url      \= env("DATABASE\_URL")  
  }

* Create .env file (add to .gitignore). Add PostgreSQL connection string and NextAuth secret:  
  \# Example for local Docker setup (KC-71) \- Adjust user/pass/db/port as needed  
  DATABASE\_URL="postgresql://user:password@localhost:5433/knowledge\_cards?schema=public"  
  NEXTAUTH\_SECRET= \# Generate with: openssl rand \-base64 32  
  \# Add other env vars as needed

* Create .env.example mirroring .env structure with placeholder values.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable):  
* Initial schema.prisma file created/configured for PostgreSQL.  
  Key Functions/Modules Involved:  
* package.json  
* prisma/schema.prisma  
* .env, .env.example  
  Testing Considerations (Technical): Verify npx prisma db push (or migrate dev) connects successfully to the PostgreSQL database once it's running (via KC-71).  
  Dependencies (Technical): KC-SETUP-1

Ticket ID: KC-SETUP-3  
Title: Install Core Frontend Dependencies  
Epic: KC-SETUP  
PRD Requirement(s): TC-STACK-1  
Team: FE  
Dependencies (Functional): KC-SETUP-1  
UX/UI Design Link: N/A  
Description (Functional): Add the necessary frontend libraries for building the user interface (Chakra UI primary), managing application state (Zustand), and implementing the block editor (BlockNote primary).  
Acceptance Criteria (Functional):

* Required libraries (@chakra-ui/react, zustand, @blocknote/react, react-flow) are listed in package.json.  
* Project dependencies install without errors.  
* The Chakra UI provider component is set up correctly in the application layout and basic styling works.  
  Technical Approach / Implementation Notes:  
* Run npm install @chakra-ui/react @emotion/react @emotion/styled framer-motion zustand @blocknote/core @blocknote/react react-flow.  
* Follow Chakra UI Next.js App Router setup guide: Create src/app/providers.tsx (client component) wrapping children with \<CacheProvider\>\<ChakraProvider\>. Import and use this in src/app/layout.tsx wrapping the main content. Ensure @chakra-ui/next-js is used for CacheProvider.  
* (Optional) Create a basic theme file src/styles/theme.ts and pass to ChakraProvider.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* package.json  
* src/app/layout.tsx  
* src/app/providers.tsx  
* src/styles/theme.ts (optional)  
  Testing Considerations (Technical): Verify basic Chakra components render correctly on default page without style conflicts.  
  Dependencies (Technical): KC-SETUP-1

Ticket ID: KC-SETUP-4  
Title: Define Basic Project Structure  
Epic: KC-SETUP  
PRD Requirement(s): NFR-MAINT-1  
Team: FE  
Dependencies (Functional): KC-SETUP-1  
UX/UI Design Link: N/A  
Description (Functional): Establish a standard folder organization within the src directory to ensure code is organized logically and consistently.  
Acceptance Criteria (Functional):

* Key folders (components, lib, styles, types, stores, hooks, app) exist within src.  
* The purpose of each main folder is briefly documented in the README or a CONTRIBUTING.md.  
  Technical Approach / Implementation Notes:  
* Create folders:  
  * src/app/ (App Router pages/layouts/APIs)  
  * src/components/ (Reusable React components \- further sub-structure by feature/type, e.g., components/auth, components/cards, components/layout)  
  * src/lib/ (Shared utilities, Prisma client instance (lib/prisma.ts), NextAuth config (lib/auth.ts), security utils (lib/security.ts))  
  * src/styles/ (Global styles, theme config)  
  * src/types/ (Shared TypeScript interfaces/types, e.g., types/index.ts, types/next-auth.d.ts)  
  * src/stores/ (Zustand state stores, e.g., stores/folderStore.ts)  
  * src/hooks/ (Custom React hooks)  
* Add brief description of folders to README.md (KC-74).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Project folder structure within src/.  
  Testing Considerations (Technical): N/A  
  Dependencies (Technical): KC-SETUP-1

Ticket ID: KC-70  
Title: Setup Code Quality Tools  
Epic: KC-SETUP  
PRD Requirement(s): NFR-MAINT-1  
Team: DO  
Dependencies (Functional): KC-SETUP-1  
UX/UI Design Link: N/A  
Description (Functional): Implement automated tools to enforce consistent code style and catch potential errors early, improving code quality and maintainability.  
Acceptance Criteria (Functional):

* Code formatting is automatically checked/applied (e.g., on save or commit).  
* Code linting rules are automatically checked.  
* Developers are prevented from committing code that violates defined style/linting rules.  
  Technical Approach / Implementation Notes:  
* Run npm install \--save-dev eslint prettier eslint-plugin-react eslint-plugin-react-hooks @typescript-eslint/parser @typescript-eslint/eslint-plugin eslint-config-prettier husky lint-staged.  
* Configure .eslintrc.json (extend next/core-web-vitals, add relevant plugins, integrate prettier). Use recommended rulesets.  
* Configure .prettierrc.json (define basic rules like semi: true, singleQuote: true, trailingComma: 'es5', printWidth: 80).  
* Add scripts to package.json: "lint": "next lint", "format": "prettier \--write \\"src/\*\*/\*.{ts,tsx,js,jsx,md,json}\\"".  
* Run npx husky init && npm install (or yarn). Edit .husky/pre-commit hook to run npm run lint && npx lint-staged. (Run lint first).  
* Configure lint-staged in package.json or .lintstagedrc.js to run prettier \--write on staged files matching pattern src/\*\*/\*.{ts,tsx,js,jsx,md,json}.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* Configuration files (.eslintrc.json, .prettierrc.json, .husky/pre-commit, .lintstagedrc.js or package.json).  
* package.json (scripts, devDependencies).  
  Testing Considerations (Technical): Verify pre-commit hook blocks commits with lint errors/formatting issues. Verify format script works.  
  Dependencies (Technical): KC-SETUP-1, Git initialized.

Ticket ID: KC-71  
Title: Create Docker Compose for Local Development DB (PostgreSQL)  
Epic: KC-SETUP  
PRD Requirement(s): TC-STACK-3, TC-STACK-7  
Team: DO/BE  
Dependencies (Functional): KC-SETUP-2  
UX/UI Design Link: N/A  
Description (Functional): Provide an easy, consistent way for developers to run the required PostgreSQL database locally using Docker Compose.  
Acceptance Criteria (Functional):

* A docker-compose.yml file exists to define the PostgreSQL service.  
* Running docker compose up \-d starts a PostgreSQL container successfully.  
* The application connects to this Dockerized database using the connection string from .env.  
* Database data persists locally between container restarts (using a Docker volume).  
* README instructions (KC-74) clearly explain how to start the local database.  
  Technical Approach / Implementation Notes:  
* Create docker-compose.yml at the project root:  
  version: '3.8'

  services:  
    db:  
      image: postgres:15 \# Use a specific version  
      container\_name: knowledge-cards-db  
      restart: always  
      ports:  
        \- "5433:5432" \# Map host port 5433 to container port 5432  
      environment:  
        POSTGRES\_USER: user \# Read from .env or set directly  
        POSTGRES\_PASSWORD: password \# Read from .env or set directly  
        POSTGRES\_DB: knowledge\_cards \# Read from .env or set directly  
      volumes:  
        \- postgres\_data:/var/lib/postgresql/data \# Persist data using a named volume  
      \# Optional: Healthcheck to ensure DB is ready before app tries connecting  
      \# healthcheck:  
      \#   test: \["CMD-SHELL", "pg\_isready \-U user \-d knowledge\_cards"\]  
      \#   interval: 10s  
      \#   timeout: 5s  
      \#   retries: 5

  volumes:  
    postgres\_data: \# Define the named volume

* **Important:** Ensure the environment variables (USER, PASSWORD, DB) in docker-compose.yml match the corresponding parts of the DATABASE\_URL in your .env file. You can directly set them here or use advanced Docker Compose features to read from .env. The port mapping (5433:5432) must also match the port in DATABASE\_URL (localhost:5433).  
* Add /docker-data/ or postgres\_data (if mapped differently) to .gitignore if necessary, although named volumes are managed by Docker outside the project directory by default.  
* Document the setup and run commands (docker compose up \-d, docker compose down) in the README (KC-74).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A (Defines infrastructure)  
  Key Functions/Modules Involved:  
* docker-compose.yml  
* .env (for connection details)  
* README.md (for instructions)  
  Testing Considerations (Technical): Verify container starts, app connects, data persists after docker compose down and docker compose up \-d. Ensure port 5433 doesn't conflict locally.  
  Dependencies (Technical): KC-SETUP-2, Docker Desktop installed.

Ticket ID: KC-74  
Title: Create Initial Project README (PostgreSQL Focus)  
Epic: KC-SETUP  
PRD Requirement(s): NFR-MAINT-1  
Team: DO  
Dependencies (Functional): KC-71  
UX/UI Design Link: N/A  
Description (Functional): Provide essential information for anyone looking at the project repository, including how to set up and run the project locally with the Dockerized PostgreSQL database.  
Acceptance Criteria (Functional):

* The README.md clearly explains the project's purpose.  
* It provides step-by-step instructions for local setup: clone, install deps, setup .env, start Docker DB, run migrations, run dev server.  
* It links to other key documents (PRD, TDD if available).  
  Technical Approach / Implementation Notes:  
* Write/Update README.md.  
* Include sections: Overview, Prerequisites (Node.js vXX+, Docker Desktop), Getting Started:  
  1. **Clone Repo:** git clone ...  
  2. **Install Deps:** npm install  
  3. **Setup Env:** Copy .env.example to .env. Fill in NEXTAUTH\_SECRET. Verify DATABASE\_URL matches Docker setup (user, password, db name, host localhost, port 5433).  
  4. **Start Database:** docker compose up \-d (Ensure Docker Desktop is running).  
  5. **Run Migrations:** npx prisma migrate dev (This applies schema changes to the running Docker DB).  
  6. **Run Dev Server:** npm run dev  
* Include sections: Tech Stack, Links, Contributing.  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* README.md  
  Testing Considerations (Technical): Have a new developer follow the README setup steps from scratch to ensure clarity and correctness.  
  Dependencies (Technical): KC-71

Ticket ID: KC-TEST-FE-1  
Title: Setup Frontend Unit Testing Framework  
Epic: KC-SETUP  
PRD Requirement(s): NFR-MAINT-1  
Team: FE/QA  
Dependencies (Functional): KC-SETUP-1, KC-SETUP-3  
UX/UI Design Link: N/A  
Description (Functional): Set up the necessary tools and configuration to allow developers to write and run automated unit tests for frontend components, ensuring code quality and preventing regressions.  
Acceptance Criteria (Functional):

* Developers can run frontend unit tests using npm run test:fe.  
* An example test for a simple component passes.  
* The setup supports testing React components using React Testing Library.  
  Technical Approach / Implementation Notes:  
* Run npm install \--save-dev @testing-library/react @testing-library/jest-dom jest jest-environment-jsdom @types/jest ts-jest. (Verify versions compatible with Next.js version).  
* Create jest.config.js. Configure using next/jest preset. Set testEnvironment: 'jest-environment-jsdom', setupFilesAfterEnv: \['\<rootDir\>/jest.setup.js'\]. Configure moduleNameMapper for aliases (e.g., @/lib/(.\*) \-\> \<rootDir\>/src/lib/$1).  
* Create jest.setup.js and import '@testing-library/jest-dom/extend-expect';.  
* Add test script to package.json: "test:fe": "jest \--watch".  
* Create src/components/Example.tsx and src/components/Example.test.tsx. Write simple test using render, screen.getByText.  
* Create test utility src/lib/test-utils.tsx to wrap render from RTL with necessary providers (e.g., ChakraProvider, mock SessionProvider).  
  API Contract (if applicable): N/A  
  Data Model Changes (if applicable): N/A  
  Key Functions/Modules Involved:  
* jest.config.js  
* jest.setup.js  
* package.json (scripts, devDependencies)  
* src/lib/test-utils.tsx  
* Example test file  
  Testing Considerations (Technical): Ensure setup handles Emotion (from Chakra) correctly. Test utility provider setup.  
  Dependencies (Technical): KC-SETUP-1, KC-SETUP-3

---
*Added Tickets Based on Review of Epic 1 Tickets & Prompts Document:*
---

Ticket ID: KC-SETUP-5
Title: Define Initial Prisma Schema Models
Epic: KC-SETUP
PRD Requirement(s): Implied by KC-3.1, NFR-MAINT-1
Team: BE
Dependencies (Functional): KC-SETUP-2 (Prisma init)
UX/UI Design Link: N/A
Description (Functional): Define the core data models required early in the project, including those needed for authentication and basic application entities, within the Prisma schema.
Acceptance Criteria (Functional):
* Prisma schema (`prisma/schema.prisma`) defines `User`, `Account`, `Session`, `VerificationToken` models matching NextAuth.js Prisma adapter requirements.
* Basic stub models for `KnowledgeCard`, `Tag`, `Folder` are defined with essential fields and basic relations (e.g., User-Card, Card-Tag many-to-many).
* Schema adheres to ADR-002 (PostgreSQL/Prisma) and ADR-004 (JSONB Content).
* Initial migration (`npx prisma migrate dev --name initial-schema`) runs successfully against the local DB (KC-71).
Technical Approach / Implementation Notes:
* Edit `prisma/schema.prisma`.
* Define models precisely as per NextAuth.js Prisma adapter docs.
* Add stub fields (id, title, content, createdAt, updatedAt, relations) for `KnowledgeCard`, `Tag`, `Folder`.
* Run `npx prisma format`.
* Run `npx prisma migrate dev --name initial-schema`.
* Run `npx prisma generate`.
Data Model Changes (if applicable): Defines core database models and creates initial migration.
Key Functions/Modules Involved: `prisma/schema.prisma`, `prisma/migrations/...`
Testing Considerations (Technical): Verify migration success and that generated Prisma client includes the new models.
Dependencies (Technical): KC-SETUP-2, KC-71

Ticket ID: KC-SETUP-6
Title: Implement Basic Layout Component
Epic: KC-SETUP
PRD Requirement(s): NFR-MAINT-1, Implied by UI Style Guide
Team: FE
Dependencies (Functional): KC-SETUP-3 (Chakra UI setup)
UX/UI Design Link: N/A (Basic structure)
Description (Functional): Create a reusable layout component to provide a consistent page structure (header, sidebar placeholder, footer, main content area) across the application.
Acceptance Criteria (Functional):
* A reusable `Layout` component exists at `src/components/layout/Layout.tsx`.
* Component uses Chakra UI for structure (Box, Flex).
* Component accepts `children` prop for main content.
* Includes placeholder sections for header, sidebar, footer.
* Integrated into the root layout (`src/app/layout.tsx`).
* Basic styling aligns with UI Style Guide.
Technical Approach / Implementation Notes:
* Create `src/components/layout/Layout.tsx`.
* Use Chakra UI `Box`, `Flex` components.
* Define simple placeholder `Box` components for Header, Sidebar, Footer.
* Render `children` in the main content area.
* Apply basic layout styles (spacing, background) from `theme.ts`.
* Import and wrap children in `src/app/layout.tsx` with this `Layout` component, inside the Chakra `Providers`.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `src/components/layout/Layout.tsx`, `src/app/layout.tsx`
Testing Considerations (Technical): Verify component renders children. Verify layout structure visually. Unit test component structure.
Dependencies (Technical): KC-SETUP-3

Ticket ID: KC-SETUP-7
Title: Configure NextAuth.js Options
Epic: KC-SETUP
PRD Requirement(s): FR-AUTH-5 (Implied setup)
Team: BE
Dependencies (Functional): KC-SETUP-2 (NextAuth install), KC-SETUP-5 (Schema), KC-SETUP-8 (Prisma Client)
UX/UI Design Link: N/A
Description (Functional): Set up the core configuration options for NextAuth.js, including the database adapter, session strategy, and initial provider setup.
Acceptance Criteria (Functional):
* NextAuth.js API route handler (`src/app/api/auth/[...nextauth]/route.ts`) exists.
* Core `authOptions` are defined (e.g., in `src/lib/auth.ts`).
* Prisma Adapter is configured using the singleton client (KC-SETUP-8) and schema models (KC-SETUP-5).
* Session strategy is set to JWT (`session: { strategy: 'jwt' }`).
* Initial `CredentialsProvider` is added with stub `authorize` function.
* `NEXTAUTH_SECRET` from `.env` (KC-SETUP-2) is referenced.
Technical Approach / Implementation Notes:
* Create `src/app/api/auth/[...nextauth]/route.ts`.
* Create `src/lib/auth.ts` and define `authOptions: NextAuthOptions`.
* Import and configure `@next-auth/prisma-adapter` with `prisma` instance from KC-SETUP-8.
* Set `providers: [ CredentialsProvider({...}) ]` with basic `authorize` stub.
* Set `session: { strategy: 'jwt' }`.
* Add placeholder callback functions (`jwt`, `session`) if needed for JWT strategy.
* Ensure `secret: process.env.NEXTAUTH_SECRET` is configured.
* Refer to Security Document Section 3.1 & 3.5.
API Contract (if applicable): N/A (Defines NextAuth endpoints)
Data Model Changes (if applicable): N/A (Uses models from KC-SETUP-5)
Key Functions/Modules Involved: `src/app/api/auth/[...nextauth]/route.ts`, `src/lib/auth.ts`, `lib/prisma.ts`
Testing Considerations (Technical): Verify API route is accessible. Unit test configuration options are set correctly. Integration test login flow later (Epic 2).
Dependencies (Technical): KC-SETUP-2, KC-SETUP-5, KC-SETUP-8

Ticket ID: KC-SETUP-8
Title: Implement Prisma Client Singleton
Epic: KC-SETUP
PRD Requirement(s): NFR-MAINT-1
Team: BE
Dependencies (Functional): KC-SETUP-2 (Prisma init)
UX/UI Design Link: N/A
Description (Functional): Implement the recommended pattern for instantiating the Prisma client to prevent multiple instances during development hot-reloading and ensure efficient connection management.
Acceptance Criteria (Functional):
* A file `src/lib/prisma.ts` exists implementing the singleton pattern.
* The pattern correctly handles `globalThis` for development environment.
* Exports a single Prisma client instance for use across the backend.
Technical Approach / Implementation Notes:
* Create `src/lib/prisma.ts`.
* Implement the pattern from Prisma documentation:
  ```typescript
  import { PrismaClient } from '@prisma/client';

  const prismaClientSingleton = () => {
    return new PrismaClient();
  };

  declare global {
    var prismaGlobal: undefined | ReturnType<typeof prismaClientSingleton>;
  }

  const prisma = globalThis.prismaGlobal ?? prismaClientSingleton();

  export default prisma;

  if (process.env.NODE_ENV !== 'production') globalThis.prismaGlobal = prisma;
  ```
* Ensure implementation aligns with ADR-002 and Coding Standards Section 4.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `src/lib/prisma.ts`
Testing Considerations (Technical): Verify client can be imported and used for queries. Manual verification during development hot-reloading.
Dependencies (Technical): KC-SETUP-2

Ticket ID: KC-SETUP-9
Title: Add .nvmrc File
Epic: KC-SETUP
PRD Requirement(s): NFR-MAINT-1
Team: DO
Dependencies (Functional): KC-SETUP-1
UX/UI Design Link: N/A
Description (Functional): Ensure consistent Node.js version usage across development environments by adding an `.nvmrc` file.
Acceptance Criteria (Functional):
* An `.nvmrc` file exists at the project root.
* The file specifies a specific LTS version from the v18 line (e.g., 18.17.0).
* Project README (KC-74) is updated to mention `.nvmrc` and recommend `nvm use`.
Technical Approach / Implementation Notes:
* Create `.nvmrc` file in the project root.
* Add a single line specifying the Node.js version (e.g., `18.17.0`).
* Update `README.md` Prerequisites section.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `.nvmrc`, `README.md`
Testing Considerations (Technical): Verify `nvm use` command works correctly in the project directory.
Dependencies (Technical): KC-SETUP-1

Ticket ID: KC-TEST-BE-1
Title: Setup Backend Unit/Integration Testing Framework
Epic: KC-SETUP
PRD Requirement(s): NFR-MAINT-1, Testing Strategy Sections 2.1, 2.2
Team: BE/QA
Dependencies (Functional): KC-SETUP-1, KC-TEST-FE-1 (Jest choice alignment)
UX/UI Design Link: N/A
Description (Functional): Set up the necessary tools and configuration to allow developers to write and run automated unit and integration tests for backend code (API routes, utilities, service logic).
Acceptance Criteria (Functional):
* Jest framework is configured for backend testing.
* A separate Jest config (e.g., `jest.config.backend.js`) exists.
* Developers can run backend tests using `npm run test:be`.
* Basic test database handling strategy is defined (e.g., scripting, test environment package).
* An example backend unit test runs successfully.
Technical Approach / Implementation Notes:
* Install dev dependencies: `jest`, `@types/jest`, `ts-jest`, potentially `supertest`, potentially `prisma-test-environment`.
* Create `jest.config.backend.js` setting `testEnvironment: 'node'` and appropriate module mappings/ignores.
* Add `"test:be": "jest --config jest.config.backend.js --watch"` script to `package.json`.
* Define and document strategy for test database management (e.g., using `prisma-test-environment` or custom setup/teardown scripts).
* Create example utility function (`src/lib/exampleUtil.ts`) and test (`src/lib/exampleUtil.test.ts`).
* Ensure alignment with Coding Standards Section 4.5.
API Contract (if applicable): N/A
Data Model Changes (if applicable): N/A
Key Functions/Modules Involved: `package.json`, `jest.config.backend.js`, test files.
Testing Considerations (Technical): Verify `npm run test:be` runs tests. Verify example test passes. Verify test database strategy is functional.
Dependencies (Technical): KC-SETUP-1, Testing framework (Jest)