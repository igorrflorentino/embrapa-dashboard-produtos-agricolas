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
  build: { outDir: 'dist', sourcemap: false },
})
