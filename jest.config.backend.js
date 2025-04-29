module.exports = {
  preset: 'ts-jest', // Use ts-jest preset
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
  // setupFilesAfterEnv: [],

  // A list of paths to directories that Jest should use to search for files in
  // roots: [
  //   "<rootDir>/src"
  // ],

  // The glob patterns Jest uses to detect test files (ignore frontend tests)
  testMatch: [
    "<rootDir>/src/**/*.test.ts",
    "!**/*.test.tsx" // Exclude files ending in .test.tsx
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
}; 