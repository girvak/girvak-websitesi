// @ts-check
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'astro/config';
import node from '@astrojs/node';
import { loadEnv } from 'vite';

// Repo-root `.env` (shared with the API and docker compose). Load it before
// reading process.env so the proxy target and `site` see the same values.
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const fromRoot = loadEnv(process.env.NODE_ENV ?? 'development', repoRoot, '');
for (const [key, value] of Object.entries(fromRoot)) {
  if (process.env[key] === undefined) process.env[key] = value;
}

// Absolute origin for canonical links, Open Graph URLs and the sitemap.
const site = process.env.PUBLIC_SITE_URL || 'https://girisimcilikvakfi.org';

export default defineConfig({
  site,

  // Server-rendered: every request reads the content API, so an Airtable edit
  // appears on the next reload. A static build would need a rebuild per change,
  // which is the thing this site is not allowed to need.
  output: 'server',
  adapter: node({ mode: 'standalone' }),

  // /sitemap.xml is a route in src/pages: in SSR the sitemap integration only
  // sees prerendered pages, and this site has four URLs.

  vite: {
    // Shared secrets and URLs live one directory up, not in frontend/.
    envDir: repoRoot,
    server: {
      // Tunnel hostnames used while sharing a dev preview.
      allowedHosts: ['.ngrok-free.dev', '.ngrok-free.app', '.ngrok.io', '.trycloudflare.com'],
      proxy: {
        // Same-origin /api and /media in dev, exactly as the reverse proxy
        // serves them in production.
        '/api': {
          target: process.env.API_BASE_URL || 'http://127.0.0.1:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
        '/media': {
          target: process.env.API_BASE_URL || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  },
});
