/**
 * Module: src/pages/sitemap.xml.ts
 * Layer: Page
 * Purpose: The sitemap, written by hand because this site has a handful of URLs (plus one per program) and the
 *          sitemap integration only sees prerendered routes in SSR.
 *
 * Called by: crawlers
 * Calls: src/lib/env.ts
 */

import type { APIRoute } from 'astro';
import { getPrograms } from '../lib/api';
import { siteUrl } from '../lib/env';

const PATHS = ['/', '/about', '/fellow-program', '/founders-ventures', '/fellows', '/alumni', '/challengers', '/board-of-trustees', '/apply', '/programs'];

export const GET: APIRoute = async () => {
  // Every program has its own page; a new Airtable row is a new URL.
  const programs = await getPrograms().catch(() => ({ categories: [] }));
  const slugs = programs.categories.flatMap((c) => c.programs.map((p) => `/programs/${p.slug}`));
  const urls = [...PATHS, ...slugs].map((path) => `  <url><loc>${siteUrl}${path}</loc></url>`).join('\n');
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`;

  return new Response(body, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};
