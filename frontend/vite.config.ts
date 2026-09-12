import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { hostname } from 'node:os';

// https://vite.dev/config/
export default defineConfig({
  base: process.env.GITHUB_PAGES ? '/bim-guard/' : '/',
  plugins: [tailwindcss(), svelte()],
  server: {
    host: '0.0.0.0',
    port: Number(process.env.PORT) || 5173,
    allowedHosts: [hostname()],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
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

