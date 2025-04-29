const nextJest = require('next/jest');

// Providing the path to your Next.js app to load next.config.js and .env files in your test environment
const createJestConfig = nextJest({ 
  dir: './' 
});

// Add any custom config to be passed to Jest
/** @type {import('jest').Config} */
const customJestConfig = {
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jest-environment-jsdom',
  moduleNameMapper: {
    // Handle module aliases (this will be automatically configured for you soon)
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  // Explicitly tell Jest to transform testing-library packages
  transformIgnorePatterns: [
    '/node_modules/(?!@testing-library/jest-dom).+\\.js$'
  ],
  // Add explicit transform for ts/tsx files using ts-jest
  transform: {
    '^.+\\.(ts|tsx)$': 'ts-jest',
  },
  // Add more setup options before each test is run
  // setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
};

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config which is async
module.exports = createJestConfig(customJestConfig); 