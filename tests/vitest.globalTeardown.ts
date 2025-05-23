// tests/vitest.globalTeardown.ts
import { TestServer } from './helpers/testServer'; // Assuming TestServer interface is exported

export async function teardown() {
  console.log('[vitest.globalTeardown.ts] Tearing down global resources...');
  const testServerInstance = (globalThis as any).__TEST_SERVER__ as TestServer | undefined;

  if (testServerInstance && typeof testServerInstance.close === 'function') {
    console.log('[vitest.globalTeardown.ts] Closing global test server...');
    try {
      await testServerInstance.close();
      console.log('[vitest.globalTeardown.ts] Global test server closed.');
    } catch (error) {
      console.error('[vitest.globalTeardown.ts] Error closing global test server:', error);
    }
  } else {
    console.warn('[vitest.globalTeardown.ts] No global test server instance found or close function missing.');
  }

  // Add any other global teardown logic here (e.g., disconnecting a global DB client if one was used)
} 