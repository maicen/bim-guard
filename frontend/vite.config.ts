import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { hostname } from 'node:os';

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

// Additional hosts that Vite's dev server will accept requests from.
// Set BIMGUARD_ALLOWED_HOSTS to a comma-separated list of LAN IPs or
// hostnames (e.g. "192.168.14.77,mypc.local") so other machines on the same
// network can reach the dev server without Vite blocking them.
// Set BIMGUARD_ALLOWED_HOSTS=* to disable the check entirely — required when
// routing through a Cloudflare Tunnel or ngrok where the hostname is an
// arbitrary external subdomain (e.g. abc123.trycloudflare.com).
// The local machine's hostname is always included automatically.
const rawAllowedHosts = process.env.BIMGUARD_ALLOWED_HOSTS ?? '';
const allowedHosts: true | string[] =
  rawAllowedHosts.trim() === '*'
    ? true // disable check — all hosts allowed (tunnel / ngrok mode)
    : [
        hostname(),
        ...rawAllowedHosts
          .split(',')
          .map((h) => h.trim())
          .filter(Boolean),
      ];

// https://vite.dev/config/
export default defineConfig({
  base: process.env.GITHUB_PAGES ? '/bim-guard/' : '/',
  plugins: [tailwindcss(), svelte()],
  server: {
    host: '0.0.0.0',
    port: Number(process.env.PORT) || 5173,
    allowedHosts: allowedHosts,
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
