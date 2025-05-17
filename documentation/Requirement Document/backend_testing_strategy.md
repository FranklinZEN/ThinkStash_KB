# Backend Testing Strategy for ThinkStash

This document outlines the strategy for testing the backend API of the ThinkStash application. The primary goal is to ensure the reliability and correctness of the API endpoints.

## Guiding Principles

1.  **Isolation**: Tests should be isolated from external dependencies (like a live database) and from each other. This ensures that a test failure points directly to the code under test and not an external factor or a side effect from another test.
2.  **Realism**: While isolated, tests should still reflect real-world usage of the API as much as possible.
3.  **Speed**: Tests should run quickly to encourage frequent execution by developers.
4.  **Maintainability**: Tests should be easy to read, understand, and update as the application evolves.

## Tools and Technologies

*   **Jest**: The primary testing framework used for its comprehensive features, including a test runner, assertion library, and mocking capabilities.
*   **`@testing-library/jest-dom`**: Used for frontend tests to provide custom matchers for DOM elements (though this document focuses on backend).
*   **`jest-mock-extended`**: Used for creating deep mocks of objects, particularly the Prisma Client, to simulate database interactions without hitting an actual database.
*   **TypeScript**: All tests are written in TypeScript to leverage static typing and improve code quality.
*   **ESM (ECMAScript Modules)**: The project (and tests) are configured to use ESM syntax (`import`/`export`).

## Current Testing Scope

The current focus is on **integration tests** for the API route handlers. These tests verify that:

*   Route handlers correctly process incoming requests (e.g., validate parameters, parse bodies).
*   Authentication and authorization logic (e.g., `getCurrentUserId`) is correctly applied.
*   Interactions with the database (via Prisma) are performed as expected (e.g., creating, reading, updating, deleting data).
*   Route handlers return appropriate HTTP responses (status codes and JSON payloads) based on the outcome of the operation.

## Mocking Strategy

### Prisma Client Mocking

The most critical dependency to mock for backend tests is the Prisma Client. This is essential for isolating tests from the database and ensuring they run predictably and quickly.

*   **Global Mock Setup (`jest.setup.backend.js`)**:
    *   A global setup file (`jest.setup.backend.js`) is configured in `jest.config.backend.js`.
    *   This file uses `jest-mock-extended` to create a deep mock of the `PrismaClient`.
    *   `jest.mock('@/lib/prisma', ...)` is used to replace the actual Prisma client instance exported from `src/lib/prisma.ts` with the mocked instance for all backend tests.
    *   The mock is reset before each test (`beforeEach`) to ensure test isolation.
    *   Specific Prisma methods (e.g., `prisma.knowledgeCard.findUnique`, `prisma.folder.create`) are then mocked on a per-test basis to return desired data or simulate specific database states (e.g., record found, record not found, database error).

*   **In-File Mocking (Alternative Example in `tests/integration/api/cards/[cardId]/route.test.ts`)**:
    *   The `route.test.ts` for cards demonstrates an alternative way to mock Prisma directly within the test file. This approach was an interim step and might be consolidated into the global mock pattern for consistency. It uses a getter in `jest.mock` to handle ESM module hoisting complexities.
    *   **Note**: While this works, using the global setup in `jest.setup.backend.js` is generally preferred for consistency and to keep test files cleaner. The `beforeEach` in the test file still resets this in-file mock (`actualPrismaMockInstance`).

### Other Mocks

*   **`getCurrentUserId` (`@/lib/sessionUtils`)**: This utility function, which likely deals with user session and authentication, is mocked using `jest.fn()` to simulate different authenticated states (e.g., a valid user ID, or no user authenticated). This allows testing of protected routes.

## Test Structure (Example: API Route Tests)

A typical API route test file (e.g., `tests/integration/api/folders/route.test.ts`) follows this structure:

1.  **Imports**: Import the route handlers (GET, POST, PUT, DELETE), necessary Next.js types (`NextRequest`, `NextResponse`), Prisma types, and mocking utilities.
2.  **Mocks**:
    *   The Prisma client is mocked (as described above, usually globally).
    *   `getCurrentUserId` is mocked.
3.  **`describe` Blocks**: Group tests by API endpoint (e.g., `/api/folders`) and then by HTTP method (e.g., `describe('POST', ...)`).
4.  **`beforeEach` Hook**:
    *   `jest.clearAllMocks()`: Clears mock call history.
    *   `mockReset(prisma)` (or the specific mock instance): Resets the state of the deep mocked Prisma client, ensuring that mock implementations from one test don't leak into another.
    *   Reset `getCurrentUserId` mock and set a default mock implementation (e.g., return a mock user ID).
5.  **`it` (or `test`) Blocks**: Individual test cases. Each test case should:
    *   **Arrange**: Set up the necessary preconditions. This includes:
        *   Mocking the return values of Prisma client methods relevant to the test (e.g., `(prisma.folder.create as jest.Mock).mockResolvedValue(...)`).
        *   Mocking `getCurrentUserId` if a specific user state is needed.
        *   Creating a `NextRequest` object with the appropriate method, headers, and body.
    *   **Act**: Execute the route handler with the request and any route parameters.
    *   **Assert**: Verify the outcome. This includes:
        *   Checking the HTTP status code of the response (`expect(response.status).toBe(...)`).
        *   Checking the JSON body of the response (`expect(await response.json()).toEqual(...)`).
        *   Verifying that Prisma client methods were called with the expected arguments (`expect(prisma.folder.create).toHaveBeenCalledWith(...)`).
        *   Verifying that `getCurrentUserId` was called.

## How to Ensure Tests Fail/Succeed for the Right Reasons (Confidence in Tests)

This is crucial for trusting your test suite. Here's how we aim for that:

1.  **Specific Assertions**:
    *   **Don't just check if *something* was returned; check if the *correct* thing was returned.** For example, if creating a folder, assert that the response body contains the title you sent and a generated ID.
    *   **Verify interactions**: Crucially, assert that your mocked functions (especially Prisma client methods) were called with the *exact arguments* you expect.
        *   `expect(prisma.folder.create).toHaveBeenCalledWith({ data: { userId: mockUserId, name: 'New Folder' } });` is much stronger than just `expect(prisma.folder.create).toHaveBeenCalled();`.
    *   **Check status codes**: Always assert the HTTP status code. A 200 is different from a 201, 400, 401, 403, 404, or 500.

2.  **Test Both Success and Failure Paths**:
    *   For every feature, test the "happy path" (everything works as expected).
    *   Equally important, test failure scenarios:
        *   **Invalid input**: What happens if the request body is malformed, or a required parameter is missing? (e.g., expect a 400 Bad Request).
        *   **Unauthorized/Unauthenticated**: What if `getCurrentUserId` returns `null` or a different user ID? (e.g., expect a 401 Unauthorized or 403 Forbidden).
        *   **Resource not found**: If trying to update or delete an item that doesn't exist or isn't owned by the user (e.g., expect a 404 Not Found).
        *   **Database errors (simulated)**: What if a Prisma call (mocked) throws an error? (e.g., expect a 500 Internal Server Error).

3.  **Keep Tests Focused (Single Responsibility)**:
    *   Each test case (`it` block) should ideally test one specific aspect or scenario. If a test fails, it should be immediately obvious what broke.
    *   Avoid overly complex tests that try to verify too many things at once.

4.  **Isolate Mocks with `mockReset`**:
    *   Using `mockReset(prisma)` (or the mock instance) in `beforeEach` is critical. It ensures that the mocked behavior for one test (e.g., `findUnique` returns a folder) doesn't accidentally affect another test (e.g., where `findUnique` should return `null`).
    *   `jest.clearAllMocks()` only clears call history (`.toHaveBeenCalledTimes`, `.toHaveBeenCalledWith`), not the mock's implementation. `mockReset` clears implementations and call history.

5.  **Understand What You're Mocking (and Why)**:
    *   **Prisma**: We mock Prisma to avoid database dependency, control data scenarios precisely, and speed up tests. We are trusting that Prisma itself works; we are testing *our use* of Prisma.
    *   **`getCurrentUserId`**: We mock this to simulate different user authentication states without needing a full authentication system active during tests.

6.  **"Red-Green-Refactor" (When Writing New Tests/Code)**:
    *   **Red**: Write a test for new functionality *before* writing the code. Run it; it should fail (because the code doesn't exist yet).
    *   **Green**: Write the minimum amount of code to make the test pass.
    *   **Refactor**: Improve the code and the test, ensuring the test still passes.
    *   This process helps ensure your tests are actually testing the behavior you intend. If a test passes immediately when you expect it to fail, your test might be flawed.

7.  **Code Coverage (as a Guide, not a Dogma)**:
    *   Tools like Jest can report code coverage. Aim for high coverage, but understand that 100% coverage doesn't guarantee bug-free code or perfectly effective tests.
    *   Focus on covering critical paths and complex logic. A test that covers a line of code but doesn't actually assert its behavior correctly is not a good test.

By following these practices, you can build a robust test suite that provides high confidence in the stability and correctness of your backend. When a test fails, it should be a reliable signal that something is wrong with the application code (or the test itself needs updating due to a valid change in requirements). When all tests pass, you should have a high degree of confidence that the system behaves as expected under the tested conditions.

## Future Enhancements

*   **Unit Tests**: For complex business logic within services or utility functions, consider adding more granular unit tests that don't involve HTTP request/response handling.
*   **End-to-End (E2E) Tests**: While out of scope for this document, a few key E2E tests (using a real database, potentially in a test environment) can provide an even higher level of confidence that all parts of the system integrate correctly. These are typically slower and more brittle, so they are used more sparingly.
*   **Contract Testing**: If other services depend on your API, contract testing can ensure that your API adheres to its defined contract, preventing breaking changes for consumers.

---

This strategy provides a solid foundation for backend testing in ThinkStash. Remember that testing is an ongoing process; review and refine your tests as the application evolves. 