# Jest Test Suite Debugging Journey: Fixes and Reference

This document summarizes the key challenges encountered and solutions implemented to achieve a fully passing Jest test suite for the project.

## Key Problem Areas & Solutions

The debugging process involved addressing several interconnected issues related to mocking, test isolation, and environment setup.

### 1. Prisma Mocking (especially `$transaction`)

*   **Initial Problem**: Tests involving Prisma transactions (notably in `tests/integration/api/folders/[folderId]/route.test.ts`) were failing. Assertions like `expect(prisma.folder.delete).toHaveBeenCalledWith(...)` reported 0 calls, or incorrect HTTP status codes were returned when database errors within transactions were simulated.
*   **Root Cause Analysis**:
    *   The `tx` object passed to the `async (tx) => {...}` callback in `prisma.$transaction(async (tx) => {...})` was not always the same `prismaMock` instance that the test files were configuring, or `$transaction` itself on the `prismaMock` instance was not a fully functional Jest mock.
    *   This was exacerbated by how `src/lib/__mocks__/prisma.ts` (using `mockDeep<PrismaClient>()`) potentially created new mock instances when imported/required by different test files or setup contexts, especially when combined with Jest configurations like `resetModules`.
*   **Fixes Implemented**:
    1.  **`src/lib/__mocks__/prisma.ts`**: Ensured this file exports a singleton `mockDeep<PrismaClient>()` instance. This is standard practice but was crucial to verify.
        ```typescript
        // src/lib/__mocks__/prisma.ts
        import { mockDeep, DeepMockProxy } from 'jest-mock-extended';
        import { PrismaClient } from '@prisma/client';

        const singletonPrismaMock = mockDeep<PrismaClient>();
        export default singletonPrismaMock;
        ```
    2.  **`jest.config.cjs` - `moduleNameMapper`**: Maintained the mapping to ensure all imports of `@/lib/prisma` point to the singleton mock:
        ```javascript
        moduleNameMapper: {
          // ...
          '^@/lib/prisma$': '<rootDir>/src/lib/__mocks__/prisma.ts',
        },
        ```
    3.  **`jest.setup.backend.cjs` - Robust `$transaction` Mocking (Key Fix)**:
        *   In the `beforeEach` block, `require('@/lib/prisma').default` is called to get the `prismaMock` instance presumably relevant to the current test file's execution context.
        *   Critically, it now defensively checks if `prismaMock.$transaction` is a full Jest mock (has `.mockImplementation`). If not (which was often the case for fresh `DeepMockProxy` instances), it wraps `prismaMock.$transaction` with `jest.fn()` to ensure it becomes a full Jest mock.
        *   Then, it reliably calls `.mockReset()` and sets `.mockImplementation(async (callback) => callback(prismaMock))`. This ensures the transaction callback receives the correctly configured `prismaMock` instance as `tx`.
        *   Model methods (like `findUnique`, `updateMany`, etc.) on `prismaMock` are reset using `.mockReset()` in this `beforeEach`.

        ```javascript
        // jest.setup.backend.cjs (simplified relevant part)
        beforeEach(() => {
          const prismaModule = require('@/lib/prisma');
          const prismaMock = prismaModule.default;

          if (prismaMock && typeof prismaMock === 'object') {
            // ... reset model methods on prismaMock using mockReset() ...

            if (prismaMock.$transaction) {
              if (typeof prismaMock.$transaction.mockImplementation !== 'function') {
                const originalTransactionFn = typeof prismaMock.$transaction === 'function' ? prismaMock.$transaction : undefined;
                prismaMock.$transaction = jest.fn(originalTransactionFn);
              }
              prismaMock.$transaction.mockReset(); 
              prismaMock.$transaction.mockImplementation(async (callback) => {
                return callback(prismaMock); 
              });
            } else { /* ... error log ... */ }
          } else { /* ... warn log ... */ }
        });
        ```
    4.  **Test File Mocks (`tests/integration/api/folders/[folderId]/route.test.ts`)**:
        *   Ensured that an explicit `jest.mock('@/lib/prisma');` at the top of this specific test file was present. This seemed necessary for this file to consistently treat methods like `prisma.folder.findUnique` as full Jest mocks from the `DeepMockProxy`.
        *   Mocked all Prisma calls within the transaction block (e.g., `prisma.knowledgeCard.updateMany`, `prisma.folder.updateMany`) to ensure the transaction didn't fail prematurely.
        *   Reverted from using a `specificDeleteMock = jest.fn()` assigned to `prisma.folder.delete` back to directly mocking `(prisma.folder.delete as jest.Mock).mockResolvedValue(...)` once the `$transaction` setup was stable.

### 2. `next-test-api-route-handler` with Next.js App Router

*   **Initial Problem**:
    *   `TypeError: next-test-api-route-handler (NTARH) initialization failed: you must provide exactly one of: pagesHandler, appHandler`.
    *   `ReferenceError: DELETE is not defined` when trying to pass a specific handler to `appHandler`.
    *   `No HTTP methods exported in 'ntarh://testApiHandler'` when passing individual functions to `appHandler`.
*   **Fix in `tests/integration/api/cards/[cardId]/route.test.ts`**:
    *   Changed from importing specific handlers (e.g., `import { GET, PUT, DELETE } from '@/app/api/cards/[cardId]/route';`) and passing the individual function (e.g., `appHandler: GET`) to:
    *   Importing the entire module: `import * as cardApiHandlerModule from '@/app/api/cards/[cardId]/route';`
    *   Passing the whole module to `testApiHandler`: `await testApiHandler({ appHandler: cardApiHandlerModule, ... });`
    *   This aligns with how `next-test-api-route-handler` expects to find the exported HTTP methods (e.g., `GET`, `POST`) as properties on the object provided to `appHandler`.

### 3. Promise-based `context.params` in App Router Handlers

*   **Problem**: Zod schema validation like `RouteParamsSchema.safeParse(context.params)` was failing in route handlers (e.g., `src/app/api/cards/[cardId]/route.ts`) with the error "Expected object, received promise".
*   **Fix**: Modified the route handlers to `await context.params` before validation:
    ```typescript
    // Example in src/app/api/cards/[cardId]/route.ts
    export async function GET(
      request: NextRequest, 
      context: { params: Promise<{ cardId: string }> } // Type updated
    ) {
      const resolvedParams = await context.params; // Await here
      const paramsValidation = CardIdParamsSchema.safeParse(resolvedParams);
      // ...
    }
    ```

### 4. Test Isolation (`resetModules` and Mock Resets)

*   **Problem**: Intermittent or context-dependent failures, where tests passed in isolation but failed when run as part of the full suite. This pointed to state leakage between tests or test files.
*   **`resetModules: true` in `jest.config.cjs`**: This was tried but caused the robust `$transaction` mocking in `jest.setup.backend.cjs` to fail because the setup file's `prismaMock` instance and the test file's `prisma` instance could become different, or the setup on the instance was lost. This option was ultimately **removed** (`resetModules: false`).
*   **`jest.resetAllMocks()` vs. Individual `mockReset()`**:
    *   `jest.resetAllMocks()` was tried in the `beforeEach` of `src/app/api/upload/image/__tests__/route.test.ts`. This was too broad and likely cleared the `$transaction` mock implementation set by `jest.setup.backend.cjs`, causing other suites to fail.
    *   Reverted to using specific `mockGetServerSession.mockReset()` and `mockHandleImageUploadLogic.mockReset()` within the `upload/image` test suite.
    *   The global `jest.setup.backend.cjs`'s `beforeEach` handles resetting Prisma client method mocks using `mockReset()`.

### 5. Syntax Errors in `.cjs` Files

*   **Problem**: `SyntaxError: Unexpected identifier 'as'` occurred in `jest.setup.backend.cjs` when TypeScript type assertion syntax (e.g., `(prismaMock.$transaction as jest.Mock)`) was inadvertently used.
*   **Fix**: Ensured all `.cjs` files (like `jest.setup.backend.cjs`) use pure JavaScript syntax, removing any TypeScript-specific syntax. Type casting is not needed if the object is already expected to be a Jest mock or is being defensively wrapped with `jest.fn()`.

### 6. Jest Path Matching on Windows

*   **Problem**: `npx jest <path_with_brackets>` (e.g., `tests/integration/api/cards/[cardId]/route.test.ts`) resulted in "No tests found" on Windows due to the `[` and `]` special characters.
*   **Fix/Workaround**:
    *   Quoting the path: `npx jest "tests/integration/api/cards/[cardId]/route.test.ts"`
    *   Using `npx jest --findRelatedTests "path/to/testfile.test.ts"` also proved effective.

## Final Configuration Highlights

*   **`jest.config.cjs`**:
    *   `clearMocks: true` (Good for clearing call counts and instances between tests within a file).
    *   `resetModules: false` (Found to be crucial for the `setupFilesAfterEnv` mock configurations to persist correctly for the intended mock instances).
    *   `moduleNameMapper`: `{'^@/lib/prisma$': '<rootDir>/src/lib/__mocks__/prisma.ts'}` correctly pointing to the singleton mock.
    *   `setupFilesAfterEnv: ['<rootDir>/jest.setup.backend.cjs']`.
*   **`src/lib/__mocks__/prisma.ts`**: Exports a single, deep-mocked Prisma client instance.
*   **`jest.setup.backend.cjs`**: Its `beforeEach` now robustly re-fetches `prismaMock` via `require` and ensures `$transaction` is a fully functional Jest mock with the correct implementation for each test run.

By systematically addressing these points, the test suite was brought to a fully passing state. 