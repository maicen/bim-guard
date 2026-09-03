import js from '@eslint/js';
import ts from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import svelteConfig from './svelte.config.js';

export default ts.config(
  js.configs.recommended,
  ...ts.configs.recommended,
  ...svelte.configs.recommended,
  {
    languageOptions: {
      globals: { ...globals.browser, ...globals.es2021 },
    },
  },
  {
    files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
    languageOptions: {
      parserOptions: {
        projectService: true,
        extraFileExtensions: ['.svelte'],
        parser: ts.parser,
        svelteConfig,
      },
    },
  },
  {
    rules: {
      // Accessibility is enforced by the Svelte 5 compiler itself and surfaced
      // through `npm run check`; eslint-plugin-svelte v3 dropped its own a11y
      // rules in favour of that. `valid-compile` re-reports those warnings here
      // so lint and typecheck agree, and `no-unused-svelte-ignore` stops stale
      // suppressions hiding real ones.
      'svelte/valid-compile': 'warn',
      'svelte/no-unused-svelte-ignore': 'warn',

      // Correctness.
      'svelte/require-each-key': 'warn',
      'svelte/valid-each-key': 'error',
      'svelte/no-dom-manipulating': 'warn',
      'svelte/no-at-html-tags': 'warn',
      'svelte/no-target-blank': 'error',
      'svelte/button-has-type': 'warn',

      // Runes-migration ratchet (Phase 4). These flag the legacy store and
      // reactivity idioms that the migration replaces.
      'svelte/prefer-svelte-reactivity': 'warn',
      'svelte/require-store-reactive-access': 'warn',
      'svelte/prefer-const': 'warn',

      // Noise reduction on a codebase that has never been linted.
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
  {
    // @typescript-eslint/no-unused-vars crashes on svelte-eslint-parser ASTs
    // (it reaches for a node `type` that the Svelte AST does not carry). The
    // Svelte compiler reports unused component state through `npm run check`,
    // so drop the duplicate here rather than losing the rule on .ts files too.
    files: ['**/*.svelte'],
    rules: {
      '@typescript-eslint/no-unused-vars': 'off',
    },
  },
  {
    ignores: ['dist/', 'node_modules/', 'public/', '.svelte-kit/', 'src/vite-env.d.ts'],
  },
);
