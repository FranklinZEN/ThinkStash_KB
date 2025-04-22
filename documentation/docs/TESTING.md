# Knowledge Card System - Testing Guide

This document outlines the testing strategy and procedures for the Knowledge Card System.

## Testing Levels

### 1. Unit Testing
- **Purpose**: Test individual components in isolation
- **Tools**: Jest, Vue Test Utils
- **Coverage Target**: 80% minimum

#### Running Unit Tests
```bash
# Run all unit tests
pnpm test:unit

# Run tests for a specific file
pnpm test:unit src/components/CardEditor.spec.ts

# Run tests with coverage
pnpm test:unit:coverage
```

### 2. Integration Testing
- **Purpose**: Test component interactions
- **Tools**: Jest, Vue Test Utils
- **Coverage Target**: 70% minimum

#### Running Integration Tests
```bash
# Run all integration tests
pnpm test:integration

# Run specific integration test
pnpm test:integration src/features/card-management.spec.ts
```

### 3. End-to-End Testing
- **Purpose**: Test complete user flows
- **Tools**: Cypress
- **Coverage Target**: Critical paths only

#### Running E2E Tests
```bash
# Start Cypress
pnpm test:e2e

# Run specific E2E test
pnpm test:e2e:spec cypress/e2e/card-creation.cy.ts
```

## Testing Guidelines

### 1. Test Structure
```typescript
describe('ComponentName', () => {
  // Setup
  beforeEach(() => {
    // Setup code
  });

  // Teardown
  afterEach(() => {
    // Cleanup code
  });

  // Test cases
  it('should do something', () => {
    // Test implementation
  });
});
```

### 2. Best Practices
- Write tests before implementing features (TDD)
- Use meaningful test descriptions
- Keep tests independent
- Mock external dependencies
- Use appropriate test data
- Follow the testing pyramid principle

### 3. Mocking Guidelines
```typescript
// Mock API calls
jest.mock('@/api/cards', () => ({
  createCard: jest.fn().mockResolvedValue({ id: '1' })
}));

// Mock Vuex store
const store = createStore({
  state: { ... },
  actions: { ... }
});
```

## Test Categories

### 1. Component Tests
- Props validation
- Event handling
- State management
- UI rendering
- User interactions

### 2. API Tests
- Request/response handling
- Error scenarios
- Authentication
- Rate limiting
- Data validation

### 3. Database Tests
- CRUD operations
- Data integrity
- Transactions
- Constraints
- Indexes

### 4. Security Tests
- Authentication
- Authorization
- Input validation
- XSS prevention
- CSRF protection

## Testing Workflow

1. **Development**
   - Write unit tests
   - Implement feature
   - Run tests locally
   - Fix any issues

2. **Code Review**
   - Review test coverage
   - Verify test quality
   - Check edge cases
   - Ensure maintainability

3. **CI/CD Pipeline**
   - Run all tests
   - Generate coverage report
   - Check for regressions
   - Deploy if passed

## Test Reports

### Coverage Reports
```bash
# Generate coverage report
pnpm test:coverage

# View coverage in browser
pnpm test:coverage:serve
```

### Test Results
```bash
# Generate test report
pnpm test:report

# View test results
pnpm test:results
```

## Common Test Scenarios

### 1. Card Management
```typescript
describe('Card Management', () => {
  it('should create a new card', async () => {
    // Implementation
  });

  it('should update an existing card', async () => {
    // Implementation
  });

  it('should delete a card', async () => {
    // Implementation
  });
});
```

### 2. Folder Management
```typescript
describe('Folder Management', () => {
  it('should create a new folder', async () => {
    // Implementation
  });

  it('should move cards between folders', async () => {
    // Implementation
  });
});
```

### 3. Search Functionality
```typescript
describe('Search', () => {
  it('should search cards by title', async () => {
    // Implementation
  });

  it('should filter cards by tags', async () => {
    // Implementation
  });
});
```

## Performance Testing

### 1. Load Testing
```bash
# Run load tests
pnpm test:load
```

### 2. Stress Testing
```bash
# Run stress tests
pnpm test:stress
```

## Security Testing

### 1. Vulnerability Scanning
```bash
# Run security scan
pnpm test:security
```

### 2. Penetration Testing
```bash
# Run penetration tests
pnpm test:penetration
```

## Continuous Integration

### GitHub Actions Workflow
```yaml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pnpm install
      - run: pnpm test
      - run: pnpm test:coverage
```

## Resources

- [Jest Documentation](https://jestjs.io/)
- [Vue Test Utils Guide](https://vue-test-utils.vuejs.org/)
- [Cypress Documentation](https://docs.cypress.io/)
- [Testing Best Practices](https://testing-library.com/docs/) 