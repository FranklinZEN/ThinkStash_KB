// tests/vitest.globalSetup.ts
// This file is no longer used for global server or Prisma setup via vitest.config.js globalSetup option.
// If other truly global, one-time setup (not Vitest API dependent) is needed, it could go here
// and be explicitly called if necessary from another script, but it's not run automatically by Vitest anymore in this strategy.

// import { makeTestServer, TestServer } from './helpers/testServer'; // No longer needed here

// let globalTestServer: TestServer | undefined; // No longer needed here

export async function setup() {
  console.log('[vitest.globalSetup.ts] Setup function called. No global server management in this strategy.');
  // No server setup here
  
  // If you had other one-time setup logic (not Vitest API dependent, not server related),
  // it could go here.

  // Return a void or no-op teardown if Vitest expects a return value
  return async () => {
    console.log('[vitest.globalSetup.ts] Global teardown called. No global server to close.');
  };
}

// No separate teardown needed if setup returns it or it's a no-op

// We don't need a separate teardown export if setup returns the teardown function.
// export async function teardown() { ... } 