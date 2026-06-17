import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The prototype JSX files reference a GLOBAL `React` (no imports) — main.jsx sets
// window.React before any component renders, so both the automatic JSX runtime
// (injected by the plugin) and direct `React.useEffect`-style calls resolve.
export default defineConfig({
  plugins: [react({ include: [/\.jsx?$/] })],
  server: {
    port: 5173,
    // The Flask BFF API (webapi) runs on :8000 in dev; prod serves SPA + /api
    // from the same origin (one Cloud Run service), so no CORS anywhere.
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
  // (not via restoreMocks, which doesn't track a direct assignment). Only the data
  // layer is covered here — chart/view rendering needs the full UI boot.
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{js,jsx}'],
    globals: false,
    restoreMocks: true,
  },
})
