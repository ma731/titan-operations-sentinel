import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies /api to the FastAPI backend so the frontend can run "live"
// without CORS config. With no backend running, the app falls back to the baked
// Friday Cascade stream (see src/cascade.js), so it always demos.
//
// Backend port defaults to 8000 (the documented default). If 8000 is taken on your
// machine, set VITE_API_PORT in webapp/frontend/.env.local (gitignored), e.g.
//   VITE_API_PORT=8009
//
// VITE_BASE is set by the GitHub Pages workflow. A project site is served from
// /<repo>/, not /, so without it every asset 404s on the deployed page. Locally it is
// unset and the base stays '/'.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiPort = env.VITE_API_PORT || '8000'
  return {
    base: env.VITE_BASE || '/',
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': { target: `http://localhost:${apiPort}`, changeOrigin: true },
      },
    },
  }
})
