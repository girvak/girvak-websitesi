/**
 * Module: src/middleware.ts
 * Layer: Layout
 * Purpose: Response headers that hold for every page: how long the HTML may be
 *          reused, and the fixed security headers. No content decision here.
 *
 * Called by: Astro, on every request
 * Calls: src/lib/env.ts
 */

import type { MiddlewareHandler } from 'astro';
import { browserCacheSeconds } from './lib/env';

// Scripts are bundled files, never inline (checked: the rendered pages carry no
// inline <script>), so script-src stays 'self'. Styles need 'unsafe-inline'
// because the design's markup carries style attributes, and Google Fonts is the
// one external origin the pages use.
const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' https: data:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join('; ');

const SECURITY_HEADERS: Record<string, string> = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  'Content-Security-Policy': CONTENT_SECURITY_POLICY,
};

export const onRequest: MiddlewareHandler = async (_context, next) => {
  const response = await next();

  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    if (!response.headers.has(name)) response.headers.set(name, value);
  }

  const isHtml = (response.headers.get('content-type') ?? '').includes('text/html');
  if (isHtml && !response.headers.has('Cache-Control')) {
    // Short on purpose: a reload is how a visitor sees an Airtable edit.
    // stale-while-revalidate keeps that reload fast while the page is refetched.
    response.headers.set(
      'Cache-Control',
      `public, max-age=${browserCacheSeconds}, stale-while-revalidate=${browserCacheSeconds * 4}`,
    );
  }

  return response;
};
