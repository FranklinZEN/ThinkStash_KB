// jest.setup.backend.cjs (CommonJS)
// console.log('####### jest.setup.backend.cjs: EXECUTING (v6) #######'); // Remove versioning comment

const { beforeEach } = require('@jest/globals');

// Define modelMethodsToClear (or modelMethodsToReset) here as it's constant
const modelMethodsToReset = {
  user: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete', 'upsert', 'count'],
  account: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete'],
  session: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete'],
  verificationToken: ['findUnique', 'findFirst', 'findMany', 'create', 'delete'],
  folder: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete', 'count'],
  knowledgeCard: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete', 'count'],
  tag: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete', 'count'],
  imageRecord: ['findUnique', 'findFirst', 'findMany', 'create', 'update', 'delete', 'count'],
};

beforeEach(() => {
  // Get the prismaMock instance afresh in EACH beforeEach.
  // This ensures we're configuring the exact instance the CURRENT test file will see.
  const prismaModule = require('@/lib/prisma');
  const prismaMock = prismaModule.default;

  // console.log(`[jest.setup.backend.cjs] beforeEach - Re-fetched prismaMock. $transaction is mock? ${!!prismaMock.$transaction?.mockImplementation}`); // Remove

  if (prismaMock && typeof prismaMock === 'object') {
    for (const modelName of Object.keys(modelMethodsToReset)) {
      if (prismaMock[modelName]) {
        for (const methodName of modelMethodsToReset[modelName]) {
          if (prismaMock[modelName][methodName] && typeof prismaMock[modelName][methodName].mockReset === 'function') {
            prismaMock[modelName][methodName].mockReset();
          }
        }
      }
    }

    if (prismaMock.$transaction) {
      let isProperMock = (typeof prismaMock.$transaction.mockImplementation === 'function') && 
                           (typeof prismaMock.$transaction.mockReset === 'function');
      
      if (!isProperMock) {
        // console.log(`[jest.setup.backend.cjs] $transaction is not a full mock initially (mockImpl: ${typeof prismaMock.$transaction.mockImplementation}, mockReset: ${typeof prismaMock.$transaction.mockReset}). Wrapping with jest.fn().`); // Remove
        const originalTransactionFn = typeof prismaMock.$transaction === 'function' ? prismaMock.$transaction : undefined;
        prismaMock.$transaction = jest.fn(originalTransactionFn);
        // console.log(`[jest.setup.backend.cjs] AFTER jest.fn() wrapper, $transaction.mockImplementation exists? ${typeof prismaMock.$transaction.mockImplementation === 'function'}`); // Remove
      }
      
      prismaMock.$transaction.mockReset(); 
      prismaMock.$transaction.mockImplementation(async (callback) => {
        return callback(prismaMock);
      });
      // console.log('[jest.setup.backend.cjs] beforeEach - $transaction configured successfully.'); // Remove
    } else {
      console.error('[jest.setup.backend.cjs] beforeEach - prismaMock.$transaction does not exist!'); // Keep this error log
    }
  } else {
    console.warn('[jest.setup.backend.cjs] prismaMock is not the expected object in beforeEach.'); // Keep this warning
  }
});