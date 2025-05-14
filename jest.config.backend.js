export default {
  // preset: 'ts-jest', // We'll define the transform directly to set useESM
  testEnvironment: 'node', // Specify Node.js environment
  // Automatically clear mock calls and instances between every test
  clearMocks: true,

  // The directory where Jest should output its coverage files
  coverageDirectory: "coverage/backend",

  // A map from regular expressions to module names or to arrays of module names that allow to stub out resources with a single module
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },

  // A list of paths to modules that run some code to configure or set up the testing framework before each test
  setupFilesAfterEnv: ['./jest.setup.backend.js'],

  // The glob patterns Jest uses to detect test files (ignore frontend tests)
  testMatch: [
    "<rootDir>/tests/integration/api/**/*.test.ts",
  ],

  // An array of regexp pattern strings that are matched against all test paths, matched tests are skipped
  // testPathIgnorePatterns: [
  //   "/node_modules/"
  // ],

  // An array of regexp pattern strings that are matched against all source file paths, matched files will skip transformation
  transformIgnorePatterns: [
    "/node_modules/",
    "\\.pnp\\.[^/]+$"
  ],

  transform: {
    '^.+\\.tsx?$': [
      'ts-jest',
      {
        useESM: true,
        // tsconfig: 'tsconfig.json', // or specific tsconfig if needed, often ts-jest finds it
      },
    ],
  },
}; 