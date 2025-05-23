// tests/vitest.setup.ts
import '@testing-library/jest-dom/vitest';
import prisma from '@/lib/prisma'; // Import actual prisma client
import { vi } from 'vitest';       // Keep for vi object if needed

// ADD PRISMA MIDDLEWARE FOR LOGGING (TEMPORARY)
if (process.env.NODE_ENV === 'test') {
  prisma.$use(async (params, next) => {
    if (params.model === 'ImageRecord' && params.action === 'create') {
      console.log('[PRISMA_MIDDLEWARE_SETUP_CREATE_ARGS] model:', params.model, 'action:', params.action, 'args:', JSON.stringify(params.args));
    }
    const result = await next(params);
    if (params.model === 'ImageRecord' && params.action === 'create' && result) {
      const resultId = (result as any)?.id;
      console.log('[PRISMA_MIDDLEWARE_SETUP_CREATE_RESULT] ID:', resultId);
    }
    return result;
  });
  console.log('[VITEST_SETUP] Prisma middleware for ImageRecord.create logging attached globally.');
} else {
  // Added more detailed log for when NODE_ENV is not 'test'
  console.log(`[VITEST_SETUP] NODE_ENV is '${process.env.NODE_ENV}', not 'test'. Prisma middleware not attached.`);
}

// All other global mocks (sessionUtils, services, MSW setup) are effectively removed or 
// should be commented out if they were causing issues.
// For instance, ensure the vi.mock for sessionUtils is also removed if it was problematic.
// vi.mock('@/lib/sessionUtils', () => ({ /* ... */ })); // Example of ensuring it's out