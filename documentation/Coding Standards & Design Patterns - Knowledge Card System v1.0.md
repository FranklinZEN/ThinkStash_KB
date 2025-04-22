## **Coding Standards & Design Patterns \- Knowledge Card System**

Version: 1.0  
Date: 2025-04-21  
Status: Draft  
**1\. Introduction**

This document defines the coding standards, conventions, and recommended design patterns for the Knowledge Card System project. The goal is to ensure code quality, consistency, maintainability, and collaboration efficiency across the team (including AI development assistants). Adherence to these standards is expected and should be reinforced through tooling (linters, formatters) and code reviews.

**2\. General Principles**

* **Readability:** Code should be easy to read and understand. Prioritize clarity over excessive cleverness. Use meaningful names and consistent formatting.  
* **Simplicity (KISS):** Keep solutions as simple as possible while meeting requirements. Avoid unnecessary complexity.  
* **DRY (Don't Repeat Yourself):** Avoid duplicating code logic. Use functions, components, and constants to promote reuse.  
* **YAGNI (You Ain't Gonna Need It):** Implement only the functionality required by the current specifications. Avoid adding features or complexity based on anticipated future needs unless explicitly planned.  
* **Consistency:** Follow the established patterns and conventions outlined in this document and demonstrated in the existing codebase.

**3\. Formatting & Linting**

* **Tooling:** We use **Prettier** for automatic code formatting and **ESLint** for identifying potential code quality issues and enforcing style rules. These are configured in KC-SETUP (.prettierrc.json, .eslintrc.json) and enforced via pre-commit hooks (husky, lint-staged).  
* **Adherence:** All committed code *must* adhere to the configured Prettier and ESLint rules. Run npm run format and npm run lint before committing.  
* **Key Styles (from Prettier config):**  
  * Max line length: 80 characters.  
  * Quotes: Single quotes (') for strings.  
  * Semicolons: Yes.  
  * Trailing Commas: es5.  
  * (Refer to .prettierrc.json for full configuration).

**4\. Naming Conventions**

* **Variables & Functions:** Use camelCase. (e.g., const cardTitle \= ..., function getUserCards() { ... })  
* **Constants:** Use UPPER\_SNAKE\_CASE for true constants (values that never change at runtime). Use PascalCase for constant components or objects where appropriate. (e.g., const MAX\_TAG\_LENGTH \= 50;, const AuthRoutes \= { ... };)  
* **Classes & Types/Interfaces:** Use PascalCase. (e.g., class AIService { ... }, interface CardData { ... }, type UserId \= string;)  
* **React Components:** Use PascalCase for component function/class names and filenames. (e.g., function FolderTree(), FolderTree.tsx)  
* **Files:**  
  * Components: PascalCase.tsx (e.g., StatsCard.tsx)  
  * Hooks: useCamelCase.ts (e.g., useDebounce.ts)  
  * Utilities/Libs: camelCase.ts or descriptive name (e.g., prisma.ts, sessionUtils.ts)  
  * API Routes (App Router): route.ts within named directories (e.g., app/api/cards/\[cardId\]/route.ts)  
  * Pages/Layouts (App Router): page.tsx, layout.tsx, loading.tsx, error.tsx.  
* **Boolean Variables:** Prefix with is, has, should, can, etc. (e.g., isLoading, hasChildren).  
* **Handlers:** Prefix event handlers with handle (e.g., handleClick, onSubmit).

**5\. TypeScript Usage**

* **Strict Mode:** Enabled via tsconfig.json. Adhere to strict type checking rules.  
* **Typing:**  
  * Prefer explicit types for function parameters and return types for clarity, especially for exported functions/modules.  
  * Use type inference for local variables where the type is obvious.  
  * Use interfaces for defining the shape of objects, especially those representing entities or API contracts. Use type for utility types, unions, intersections, or simple aliases.  
  * Avoid any wherever possible. Use unknown for values where the type is truly unknown and perform type checking/casting. Use specific types or generics instead.  
  * Use Readonly\<T\> or readonly modifiers for immutable data structures where appropriate.  
* **Enums:** Use TypeScript enum or string literal unions (type Status \= 'pending' | 'success' | 'error';) based on context. Prefer string literal unions for simple, fixed sets of values.  
* **Non-null Assertion (\!):** Avoid using the non-null assertion operator (\!) unless you are absolutely certain a value cannot be null/undefined based on prior checks or application logic that TypeScript cannot infer. Prefer explicit checks or optional chaining (?.).

**6\. React & Next.js Conventions**

* **Components:**  
  * Use **Functional Components** with Hooks almost exclusively.  
  * Keep components small and focused on a single responsibility (Single Responsibility Principle).  
  * Prefer composition over inheritance.  
  * Use descriptive prop names. Define prop types using TypeScript interfaces.  
  * Avoid prop drilling; use State Management (Zustand) or React Context for deeply shared state.  
  * Use 'use client' directive only when necessary (for components using Hooks like useState, useEffect, event handlers, or browser APIs). Keep Server Components as the default where possible for performance.  
* **Hooks:**  
  * Follow Rules of Hooks (call only at top level, not inside loops/conditions).  
  * Create custom hooks (useSomething) to encapsulate reusable stateful logic or side effects.  
* **State Management:**  
  * Use **Zustand** for managing global or cross-component state (as decided in KC-SETUP-3). Define stores in src/stores/. Structure stores logically (e.g., by feature).  
  * Use React Context for simple, low-frequency state sharing within specific subtrees if Zustand feels like overkill.  
  * Use component local state (useState, useReducer) for state confined to a single component or its immediate children.  
* **Styling:**  
  * Use **Chakra UI** components and style props primarily.  
  * Use the defined theme (src/styles/theme.ts) for consistent spacing, colors, typography. Avoid hardcoding style values directly in components.  
  * Use semantic Chakra components where appropriate (Heading, Text, List, etc.).  
* **App Router:**  
  * Follow Next.js App Router conventions for file-based routing (page.tsx, layout.tsx).  
  * Use Route Groups ((groupName)) for organizing routes without affecting URL paths (e.g., (protected)).  
  * Use dynamic segments (\[segmentName\]) for parameterized routes.  
  * Utilize loading.tsx and error.tsx for automatic UI handling.  
  * Fetch data in Server Components where possible for performance. Use Route Handlers (route.ts) for API endpoints.  
* **Data Fetching (Client):**  
  * Prefer using libraries like **SWR** or **React Query** (TanStack Query) for client-side data fetching, caching, and state synchronization, especially for data that changes or needs revalidation (e.g., folder list, stats). Basic fetch in useEffect is acceptable for simpler cases initially.  
  * Handle loading and error states explicitly in the UI.

**7\. Backend & API Conventions**

* **API Routes (Next.js Route Handlers):**  
  * Place handlers in src/app/api/.../route.ts.  
  * Keep handlers focused: primarily responsible for request validation, calling service/logic functions, and formatting responses.  
  * Extract complex business logic into separate utility or service functions (src/lib/...).  
* **Request/Response:**  
  * Use standard HTTP methods correctly (GET, POST, PUT, DELETE).  
  * Validate request bodies and parameters rigorously using **Zod**.  
  * Return consistent JSON response shapes for success and errors.  
    * Success: { data: ... } or direct object/array.  
    * Error: { error: "Error message" } or { errors: { field?: string\[\], ... } } for validation.  
  * Use appropriate HTTP status codes (200, 201, 204, 400, 401, 403, 404, 409, 500).  
* **Error Handling:**  
  * Use try/catch blocks for operations that can fail (DB queries, API calls, file system access).  
  * Log errors server-side with sufficient context (use a structured logger like Pino \- to be added via KC-OPS).  
  * Return meaningful (but not overly technical) error messages to the client. Distinguish between client errors (4xx) and server errors (5xx).  
* **Prisma Usage:**  
  * Instantiate Prisma Client once and reuse it (lib/prisma.ts).  
  * Use Prisma's generated types.  
  * Leverage Prisma's relation queries and include/select options.  
  * Use transactions (prisma.$transaction) for multi-step operations that need atomicity.  
  * Handle potential Prisma errors (e.g., P2002 for unique constraints, P2025 for record not found on update/delete).  
* **Security:** Implement authorization checks (user ownership) in *all* relevant API routes (KC-8.2).

**8\. Comments & Documentation**

* **Comments:** Explain the *why*, not the *what*. Assume the reader understands the language basics. Comment complex logic, workarounds, or non-obvious decisions. Avoid commenting obvious code. Keep comments up-to-date.  
* **JSDoc / TSDoc:** Use for documenting exported functions, classes, types, and complex internal functions, especially in shared libraries (src/lib). Describe parameters (@param), return values (@returns), and purpose.  
* **TODOs:** Use // TODO: comments for minor pending tasks, but prefer creating actual tickets for anything significant. Include context or ticket reference if possible.

**9\. Testing**

* **Strategy:** Refer to the Testing Strategy document (to be generated).  
* **Frameworks:** Use Jest/Vitest with React Testing Library for frontend unit/integration tests. Backend tests use Jest/Vitest. E2E tests (Stage 2+) likely use Cypress or Playwright.  
* **Naming:** Test files adjacent to the component/module being tested (ComponentName.test.tsx, utils.test.ts).  
* **Structure:** Use describe, it, beforeEach, etc., logically. Write clear test descriptions.  
* **Mocking:** Mock dependencies (API calls, modules, hooks) appropriately using jest.mock or library-specific utilities. Keep mocks focused.  
* **Coverage:** Aim for defined coverage targets (NFR-MAINT-3: Unit 80%, Integration 60%), focusing on critical paths and complex logic.

**10\. Git Workflow & Commit Messages**

* **Branching:** Use a Gitflow-like strategy (e.g., main, develop, feature/ticket-id-description, fix/ticket-id-description, release/version). Create Pull Requests (PRs) for merging features/fixes into develop (or main directly if simpler workflow preferred).  
* **Commits:** Write clear, concise commit messages following the Conventional Commits format (e.g., feat: Add folder creation API, fix: Correct validation for card title, refactor: Improve search query logic, test: Add unit tests for AuthForm, docs: Update README setup instructions).  
* **PRs:** Require at least one approval before merging (configure in GitHub). Ensure CI checks (lint, test, build) pass. Include link to relevant JIRA ticket(s).

## **Tech Lead Review & Assessment (Coding Standards v1.0)**

This document provides a comprehensive starting point for coding standards and patterns tailored to our tech stack (Next.js, TypeScript, React, Prisma, Chakra UI, Zustand).

**Strengths:**

* Covers key areas from formatting to architecture patterns.  
* References specific tools and libraries chosen for the project.  
* Provides actionable conventions (naming, typing, etc.).  
* Establishes a baseline for code quality and consistency.

**Areas for Clarification / Team Discussion:**

* **Specific Pattern Preferences:** Does the team have strong existing preferences for certain patterns not explicitly detailed here (e.g., specific ways to structure Zustand stores, advanced React patterns)?  
* **Error Handling Details:** While outlining the strategy, specific formats for structured error responses or logging could be further defined.  
* **Git Workflow Rigor:** Is the proposed Gitflow-like branching strategy suitable, or would a simpler trunk-based development model be preferred? How strictly should Conventional Commits be enforced?  
* **ADR Usage:** Should we formally adopt Architecture Decision Records (ADRs) for significant technical choices? (TL recommends Yes).

**Questions for PM/Stakeholders:**

* *(Generally fewer PM questions for coding standards, more for team alignment)* Are there any high-level principles or existing company-wide standards that need to be incorporated?

**TL Recommendations & Alternatives:**

* **Consistency is Key:** The most important aspect is *consistent application* of these standards. Code reviews are crucial for enforcement and discussion.  
* **Tooling:** Leverage ESLint and Prettier maximally. Consider adding more specific ESLint plugins (e.g., eslint-plugin-react-hooks, eslint-plugin-jsx-a11y, potentially custom rules).  
* **Evolution:** This document should be considered "living". As the project evolves and the team encounters new challenges or adopts new patterns, update the standards accordingly.  
* **Onboarding:** Use this document as part of the onboarding process for new developers (including AI assistants).  
* **ADRs:** Recommend formally using ADRs (template to be provided) to document significant architectural decisions and their rationale.

**Draft Rating:**

* **Completion:** 4.5 / 5.0 (Covers essential areas for the chosen tech stack).  
* **Quality/Accuracy:** 4.0 / 5.0 (Provides solid, standard recommendations. Quality increases with team buy-in and consistent enforcement. Needs minor refinement based on team discussion).

This document sets the foundation for how we write code. Consistent adherence will greatly benefit maintainability and collaboration.

Ready to move on to the next document? Perhaps the **Architecture Decision Records (ADRs)**?