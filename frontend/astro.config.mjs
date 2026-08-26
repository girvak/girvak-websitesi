// @ts-check
import { defineConfig } from 'astro/config';
import node from '@astrojs/node';

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
