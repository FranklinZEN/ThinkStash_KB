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
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@/lib/prisma$': '<rootDir>/src/lib/__mocks__/prisma.ts', // Ensures singleton mock
  },
  setupFiles: ['<rootDir>/jest.polyfills.cjs'],
  setupFilesAfterEnv: ['<rootDir>/jest.setup.backend.cjs'],
  testMatch: [
    "<rootDir>/tests/integration/api/**/*.test.ts",
    "<rootDir>/src/**/__tests__/**/*.test.ts",
  ],
};

module.exports = nextJest(customJestConfig);