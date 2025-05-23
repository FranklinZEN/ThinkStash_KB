import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  test: {
    globals: true,
    environment: 'happy-dom', // Start with happy-dom
    setupFiles: ['./tests/vitest.setup.ts', './tests/vitest.globalSetup.ts'],
    reporters: ['default', 'html'], // Optional: for HTML reports
    coverage: {
      provider: 'v8', // or 'istanbul'
      reporter: ['text', 'json', 'html', 'lcov'],
      exclude: [
        // Standard exclusions
        '**/node_modules/**',
        '**/dist/**',
        '**/build/**',
        '**/.next/**',
        '**/.vercel/**',
        '**/.husky/**',
        '**/.vscode/**',
        '**/coverage/**',
        
        // Config files
        '**/*.config.js',
        '**/*.config.ts',
        '**/*.config.cjs',
        '**/*.config.mjs',
        
        // Entry points / public assets
        '**/main.tsx',
        '**/main.ts',
        '**/public/**',
        
        // Test files and mocks themselves
        '**/tests/**',
        '**/__tests__/**',
        '**/__mocks__/**',
        '**/*.test.ts',
        '**/*.spec.ts',
        '**/*.test.tsx',
        '**/*.spec.tsx',
        '**/vitest.setup.ts',
        
        // Type definitions
        '**/*.d.ts',

        // Other specific exclusions if known
        '**/generated/**', // Prisma generated client
        '**/prisma/seed.ts', // Prisma seed file
        // 'src/app/layout.tsx', // Example: if layout has no testable logic
        // 'src/app/page.tsx',     // Example: if page is simple
      ],
    },
    // Optional: environment options for happy-dom or jsdom
    // environmentOptions: {
    //   happyDOM: { /* happy-dom specific options */ }
    // },
  },
}); 