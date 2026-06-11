// ESLint flat config — scoped to the HAND-WRITTEN layer ONLY.
//
// The frontend is the design-system's React/Vite prototype reused verbatim
// (src/proto/, including the 700KB vendored src/proto/_ds_bundle.js). Only the
// API-backed data layer (src/data/) and the Plotly.js charts (src/charts/) are
// ours, so those are the only two trees we lint — globally ignoring everything
// else keeps the vendor prototype's style out of scope (it would drown real
// findings in noise we don't own).
//
// Ruleset: eslint:recommended (JS correctness) + react-hooks recommended (the
// charts already carry react-hooks/exhaustive-deps disable comments, so the
// plugin is the one we expect to fire). React itself is a runtime global
// (main.jsx sets window.React; the Vite plugin injects the automatic JSX
// runtime) — see vite.config.js — so we don't run eslint-plugin-react's
// component rules. The ONE react rule we DO need is jsx-uses-vars: components
// referenced only in JSX (e.g. <Plot/>, <BarChart/>) look "unused" to core
// no-unused-vars without it. The browser globals below cover
// window/document/fetch/etc.

import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  // Lint nothing by default; the scoped block below opts the two owned trees in.
  // Everything else (proto/, the vendored bundle, dist/, node_modules/) is out.
  {
    ignores: ['src/proto/**', 'dist/**', 'node_modules/**', '*.config.js'],
  },

  {
    files: ['src/data/**/*.{js,jsx}', 'src/charts/**/*.{js,jsx}'],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.browser,
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
