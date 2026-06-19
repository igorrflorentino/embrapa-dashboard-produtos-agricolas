// ESLint flat config — the hand-maintained app code.
//
// src/ui/ began as the design-system's React/Vite UI (adopted from the handoff),
// but it is now the LIVE production UI the team actively edits (the synthetic data
// layer was replaced with API calls, proto/→ui/, new views added), so it is linted
// too — the same correctness ruleset as the data/charts layers. Earlier it was
// globally ignored as "imported style we don't own"; that rationale lapsed once it
// became maintained prod code, and the gap was hiding real dead-code + hook-deps
// findings.
//
// Ruleset: eslint:recommended (JS correctness) + react-hooks recommended (some
// chart/view files carry react-hooks/exhaustive-deps disable comments, so the
// plugin is the one we expect to fire). React itself is a runtime global
// (main.jsx sets window.React; the Vite plugin injects the automatic JSX
// runtime) — see vite.config.js — so we don't run eslint-plugin-react's
// component rules and we declare `React` as a global below to avoid false
// no-undef on the import-less UI files. The ONE react rule we DO need is
// jsx-uses-vars: components referenced only in JSX (e.g. <Plot/>, <BarChart/>)
// look "unused" to core no-unused-vars without it. The browser globals below
// cover window/document/fetch/etc.

import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  // Lint nothing by default; the scoped block below opts the owned trees in.
  {
    ignores: ['dist/**', 'node_modules/**', '*.config.js'],
  },

  {
    files: ['src/data/**/*.{js,jsx}', 'src/charts/**/*.{js,jsx}', 'src/ui/**/*.{js,jsx}'],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.browser,
        // main.jsx assigns window.React; the import-less UI/chart files read it.
        React: 'readonly',
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      react,
      'react-hooks': reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Mark components used in JSX as "used" so no-unused-vars doesn't flag
      // <Plot/>/<BarChart/> imports/decls (core ESLint doesn't parse JSX usage).
      'react/jsx-uses-vars': 'error',
      // Leading-underscore vars are intentional throwaways. args:'none' because
      // React prop destructuring legitimately accepts props a given chart
      // ignores (e.g. BrazilTileMap takes `height` but sizes via CSS/viewBox).
      'no-unused-vars': ['error', { args: 'none', varsIgnorePattern: '^_' }],
      // Empty catch blocks are a deliberate "keep the other subscribers alive"
      // pattern throughout the data layer; allow them when explicitly emptied.
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },

  // Test files (Vitest) — describe/it/expect/vi are imported, but add the
  // Node/Vitest timer + global helpers they touch (setTimeout, etc.).
  {
    files: ['src/**/*.test.{js,jsx}'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
];
