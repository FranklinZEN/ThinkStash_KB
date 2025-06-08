import { FlatCompat } from '@eslint/eslintrc';

const compat = new FlatCompat();

const config = [
  {
    ignores: [
      'node_modules/**',
      '.next/**',
      'out/**',
      'build/**',
      'generated/**',
      'eslint.config.js',
      '.venv/**',
      'dist/**',
      'coverage/**',
      'public/**',
      'documentation/**',
      'aiservice/.venv/**',
    ],
  },
  ...compat.extends('next/core-web-vitals'),
  ...compat.extends('plugin:@typescript-eslint/recommended'),
  ...compat.extends('prettier'),
  {
    files: ["**/*.ts", "**/*.tsx"],
    rules: {
      '@typescript-eslint/no-unused-vars': ['warn', {
        varsIgnorePattern: '^_',
        argsIgnorePattern: '^_',
        ignoreRestSiblings: true
      }],
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },
];

export default config; 