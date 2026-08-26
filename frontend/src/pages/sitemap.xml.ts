/**
 * Module: src/pages/sitemap.xml.ts
 * Layer: Page
 * Purpose: The sitemap, written by hand because this site has four URLs and the
 *          sitemap integration only sees prerendered routes in SSR.
 *
 * Called by: crawlers
 * Calls: src/lib/env.ts
 */

import type { APIRoute } from 'astro';
import { siteUrl } from '../lib/env';

const PATHS = ['/', '/about', '/fellow-program', '/board-of-trustees'];

export const GET: APIRoute = () => {
  const urls = PATHS.map((path) => `  <url><loc>${siteUrl}${path}</loc></url>`).join('\n');
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
