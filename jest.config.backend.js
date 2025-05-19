console.log('jest.config.backend.js: EXECUTING CONFIGURATION'); // Diagnostic log
const nextJest = require('next/jest')({
  dir: './', // Path to your Next.js app to load next.config.js and .env files
});

// Add any custom Jest config to be passed to the Next.js preset
const customJestConfig = {
  testEnvironment: 'node',
  clearMocks: true,
  // coverageDirectory: "coverage/backend", // You can keep this if you use coverage
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    // No longer explicitly mapping @/lib/prisma due to DI in service and __mocks__ convention
  },
  setupFiles: ['<rootDir>/jest.polyfills.js'], // Polyfills run before environment setup
  setupFilesAfterEnv: ['./jest.setup.backend.mjs'], // For mocks and other setup after env
  testMatch: [
    // Adjust if next/jest has different defaults or if you want to keep current structure
    "<rootDir>/tests/integration/api/**/*.test.ts", 
    "<rootDir>/src/**/__tests__/**/*.test.ts",
    // "<rootDir>/src/**/*.test.ts" // if you have other src tests
  ],
  // transform: {}, // next/jest handles transformation via SWC, so ts-jest transform is removed
  // testEnvironmentOptions: { // next/jest should set up the environment correctly; remove this for now
  //   customExportConditions: ['node', 'node-addons'],
  // },
  // extensionsToTreatAsEsm: ['.ts'], // next/jest should handle ESM based on your Next.js config
};

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config which is async
module.exports = nextJest(customJestConfig); 