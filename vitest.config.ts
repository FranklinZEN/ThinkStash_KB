import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths'; // <<< UNCOMMENTED
import path from 'path'; // Import path module

export default defineConfig({
  plugins: [react(), tsconfigPaths()], // <<< RE-ADDED tsconfigPaths()
  test: {
    globals: true,
    environment: 'happy-dom', // Default environment, can be overridden per-file
    // setupFiles is for scripts that run before each test file
    setupFiles: ['./tests/vitest.setup.ts'], 
    reporters: ['default', 'html'], // Optional: for HTML reports
    testTimeout: 30000, // Increased to 30000
    hookTimeout: 30000, // Increased to 30000
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
    // alias: { // <<< TEMPORARILY COMMENT OUT THIS BLOCK
    //   '@/': path.resolve(__dirname, './src'),
    //   '@/components/': path.resolve(__dirname, './src/components'),
    //   '@/app/': path.resolve(__dirname, './src/app'),
    //   '@/lib/': path.resolve(__dirname, './src/lib'),
    //   '@/styles/': path.resolve(__dirname, './src/styles'),
    //   '@/public/': path.resolve(__dirname, './public'),
    //   '@/tests/': path.resolve(__dirname, './tests'), 
    //   '@/mocks/': path.resolve(__dirname, './src/mocks'),
    // },
    // Optional: environment options for happy-dom or jsdom
    // environmentOptions: {
    //   happyDOM: { /* happy-dom specific options */ }
    // },
  },
}); 