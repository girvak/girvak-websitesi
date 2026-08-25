// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// `site` is used for canonical URLs and the sitemap. Override per environment
// with PUBLIC_SITE_URL (e.g. the production domain).
const site = process.env.PUBLIC_SITE_URL || 'https://girisimcilikvakfi.org';

export default defineConfig({
  site,
  integrations: [sitemap()],
  // Static output (SSG) — best SEO + speed for a content site.
  output: 'static',
  vite: {
    server: {
      // Allow ngrok / Cloudflare tunnel hostnames in dev.
      allowedHosts: ['.ngrok-free.dev', '.ngrok-free.app', '.ngrok.io', '.trycloudflare.com'],
      proxy: {
        // Same-origin /api in dev (newsletter + refresh) — works through ngrok.
        '/api': { target: process.env.API_BASE_URL || 'http://127.0.0.1:8000', changeOrigin: true },
        // Mirrored Airtable attachments (non-expiring image URLs) — same host as /api.
        '/media': { target: process.env.API_BASE_URL || 'http://127.0.0.1:8000', changeOrigin: true },
      },
    },
  },
});
