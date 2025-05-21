// jest.setup.backend.cjs (CommonJS)
// console.log('####### jest.setup.backend.cjs: EXECUTING (v6) #######'); // Remove versioning comment

const { beforeEach } = require('@jest/globals');
// const { mockReset } = require('jest-mock-extended'); // Remove this import

// Define modelMethodsToReset
const modelMethodsToReset = {
  user: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete', 'upsert', 'count'],
  account: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete'],
  session: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete'],
  verificationToken: ['findUnique', 'findFirst', 'findMany', 'create', 'delete'],
  folder: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete', 'count'],
  knowledgeCard: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete', 'count'],
  tag: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete', 'count'],
  imageRecord: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete', 'count'],
  // Add other models and their methods as needed
};

beforeEach(() => {
  // No specific Prisma reset logic here anymore.
  // jest.config.js has clearMocks: true, which should handle basic mock clearing.
  // Individual tests can manage their specific mock implementations or use .mockReset() if needed.

  // Example: If other global mocks needed resetting, it would go here.
  // e.g. someOtherGlobalMock.mockReset();
});