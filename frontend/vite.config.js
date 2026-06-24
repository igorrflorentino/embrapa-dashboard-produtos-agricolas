import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The UI JSX files reference a GLOBAL `React` (no imports) — bootstrap-globals sets
// window.React before any component evaluates, so direct `React.useEffect`-style calls
// resolve. The JSX-runtime choice is scoped by environment:
//   • Dev server (rolldown-vite): the AUTOMATIC runtime's Babel transform emits a CJS
//     `require("react/jsx-dev-runtime")` that the rolldown-vite dev server does NOT
//     rewrite to ESM — that "require is not defined" broke `npm run dev` for every UI
//     module (while the build stayed green). The CLASSIC runtime compiles JSX to
//     `React.createElement(...)`, resolving the same global window.React, with no import.
//   • Build + Vitest: keep the AUTOMATIC runtime they already pass on (the build bundles
//     the ESM jsx-runtime import fine; Vitest has no global React, which the classic
//     runtime would require). Vitest also runs under command 'serve', hence the VITEST guard.
export default defineConfig(({ command }) => {
  const isDevServer = command === 'serve' && !process.env.VITEST
  return {
    plugins: [react({ jsxRuntime: isDevServer ? 'classic' : 'automatic', include: [/\.jsx?$/] })],
    server: {
      port: 5173,
      // The Flask BFF API (webapi) runs on :8000 in dev; prod serves SPA + /api
      // from the same origin (one Cloud Run service), so no CORS anywhere.
      proxy: { '/api': 'http://127.0.0.1:8000' },
    },
    // `vite preview` (serving the built dist) mirrors the dev proxy, so a production
    // build can be smoke-tested against the local webapi the same way `npm run dev` is.
    preview: {
      port: 4173,
      proxy: { '/api': 'http://127.0.0.1:8000' },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      // Split the heavy vendor code into separate, long-lived cacheable chunks so
      // the app shell isn't a single 1.6MB file: Plotly (~1MB) and React load in
      // parallel and stay cached across app-code deploys.
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules/plotly.js')) return 'plotly';
            if (id.match(/node_modules\/(react|react-dom|scheduler)\//)) return 'react';
            return undefined;
          },
        },
      },
      chunkSizeWarningLimit: 1200, // Plotly is legitimately ~1MB; don't warn on it
    },
    // Vitest reads this `test` block from the Vite config. jsdom gives the data-layer
    // modules a real `window` (they assign window.dataStore/enrichment and read the
    // UI registries). Each suite reassigns globalThis.fetch in its load() helper
    // (not via restoreMocks, which doesn't track a direct assignment).
    test: {
      environment: 'jsdom',
      include: ['src/**/*.test.{js,jsx}'],
      globals: false,
      restoreMocks: true,
    },
  }
})
