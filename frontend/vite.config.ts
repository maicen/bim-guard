import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Where `/api` and `/static` are proxied. Both default to the single-stack
// port, so nothing changes for the usual one-checkout setup.
//
// It is overridable because `/static/js/viewer/ifc-viewer.js` is fetched at
// runtime rather than bundled (see IfcViewer.svelte's dynamic import and the
// `external` rule below), so the proxy target decides which checkout's viewer
// the browser actually runs. With two checkouts open, the second backend binds
// 8001 while its frontend still proxied to 8000 -- serving the *other* tree's
// viewer, so edits here had no effect and the console showed none of this
// tree's logging. Point this at the backend belonging to this checkout:
//
//   BIMGUARD_BACKEND_URL=http://127.0.0.1:8001 PORT=5174 npm run dev
const backendTarget = process.env.BIMGUARD_BACKEND_URL || 'http://127.0.0.1:8000';

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte()],
  server: {
    host: '0.0.0.0',
    port: Number(process.env.PORT) || 5173,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/static': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      external: [/^\/static\/.*/],
    },
  },
});
