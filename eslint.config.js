// eslint.config.js
import nextConfig from 'eslint-config-next';
import prettierConfig from 'eslint-config-prettier';

export default [
  {
    ignores: [
      "node_modules/**", ".next/**", "out/**", "build/**",
      "generated/**", ".venv/**", "dist/**", "coverage/**",
      "public/**", "documentation/**", "aiservice/.venv/**"
    ]
  },

  // Use the Next.js config as the primary source of truth.
  nextConfig,

  // Your project-specific rule overrides.
  {
    rules: {
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['warn', {
        "varsIgnorePattern": "^_",
        "argsIgnorePattern": "^_",
        "ignoreRestSiblings": true
      }],
    }
  },

  // Add Prettier config LAST to disable conflicting style rules.
  prettierConfig,
]; 