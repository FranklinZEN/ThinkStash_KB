// jest.config.cjs
console.log('jest.config.cjs: EXECUTING CONFIGURATION (Corrected)');
const nextJest = require('next/jest')({
  dir: './', // Path to your Next.js app to load next.config.js and .env files
});

// Add any custom Jest config to be passed to the Next.js preset
const customJestConfig = {
  testEnvironment: 'node',
  clearMocks: true, // Keeps mocks' implementations but clears calls/instances
  // resetModules: true, // Removed as it caused issues with setupFilesAfterEnv persistence
  moduleNameMapper: {
    // General alias for @/ pointing to src/
    '^@/(.*)$': '<rootDir>/src/$1',

    // Ensure @/lib/prisma always resolves to the same source file.
    // The jest.mock in setup-tests.ts targets the alias '@/lib/prisma'.
    '^@/lib/prisma(\.js|\.ts)?$': '<rootDir>/src/lib/prisma.ts',

    // Canonicalize sessionUtils path
    '^@/lib/sessionUtils(\.js|\.ts)?$': '<rootDir>/src/lib/sessionUtils.ts',
    // Add relative path mappers if sessionUtils might be imported relatively
    '^\.\./\.\./\.\./lib/sessionUtils(\.js|\.ts)?$': '<rootDir>/src/lib/sessionUtils.ts',
    '^\.\./lib/sessionUtils(\.js|\.ts)?$': '<rootDir>/src/lib/sessionUtils.ts',

    // Canonicalize paths for cardService to ensure jest.mock in setup-tests.ts hits it
    // This maps both the alias and potential relative paths to the same source file.
    // The jest.mock in setup-tests.ts targets '@/lib/services/cardService'.
    '^@/lib/services/cardService(\.js|\.ts)?$': '<rootDir>/src/lib/services/cardService.ts',
    '^\.\./\.\./\.\./lib/services/cardService(\.ts)?$': '<rootDir>/src/lib/services/cardService.ts',
    // Add more relative path patterns if necessary, e.g., from different depths
    '^\.\./lib/services/cardService(\.js|\.ts)?$': '<rootDir>/src/lib/services/cardService.ts',

    // Canonicalize paths for folderService
    '^@/lib/services/folderService(\.js|\.ts)?$': '<rootDir>/src/lib/services/folderService.ts',
    '^\.\./\.\./\.\./lib/services/folderService(\.js|\.ts)?$': '<rootDir>/src/lib/services/folderService.ts',
    '^\.\./lib/services/folderService(\.js|\.ts)?$': '<rootDir>/src/lib/services/folderService.ts',

    // NOTE: The moduleNameMapper for '@/lib/prisma' was removed as prisma is mocked in setup-tests.ts
    // using jest.mock('@/lib/prisma', ...), which is the preferred way if paths are consistent.
    // If prisma import paths were also inconsistent, a similar canonicalization could be done for it.
  },
  setupFiles: ['<rootDir>/jest.polyfills.cjs'],
  // Updated setupFilesAfterEnv
  setupFilesAfterEnv: ['<rootDir>/tests/setup-tests.ts'], 
  testMatch: [
    "<rootDir>/tests/integration/api/**/*.test.ts",
    "<rootDir>/src/**/__tests__/**/*.test.ts",
  ],
};

module.exports = nextJest(customJestConfig);