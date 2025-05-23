// tests/vitest.globalSetup.ts
// This file is no longer used for global server or Prisma setup via vitest.config.js globalSetup option.
// If other truly global, one-time setup (not Vitest API dependent) is needed, it could go here
// and be explicitly called if necessary from another script, but it's not run automatically by Vitest anymore in this strategy.

export async function setup() {
  console.log('[vitest.globalSetup.ts] Setup function called (but no longer setting up server/Prisma globally).');
  // Previous server and Prisma setup logic removed.
}

export async function teardown() {
  console.log('[vitest.globalSetup.ts] Teardown function called (but no longer tearing down server/Prisma globally).');
  // Previous server teardown logic removed.
} 