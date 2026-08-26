/**
 * Module: src/lib/env.ts
 * Layer: Lib
 * Purpose: The only place the environment is read. Validates on first use, so a
 *          missing value fails at boot instead of rendering a broken page.
 *
 *          Reads `process.env` first: in an SSR build `import.meta.env` values
 *          are inlined at build time, and this site must be reconfigurable by
 *          restarting the process, never by rebuilding it.
 *
 * Called by: src/lib/api.ts, src/pages/*
 * Calls: nothing
 */

/** Read one variable at request time, with the dev-server value as the fallback. */
function raw(name: string): string {
  const fromProcess = typeof process !== 'undefined' ? process.env?.[name] : undefined;
  return String(fromProcess ?? import.meta.env[name] ?? '').trim();
}

/** Where the server-rendered pages read content from. Never sent to the browser. */
export const apiBaseUrl: string = readUrl('API_BASE_URL', 'http://127.0.0.1:8000');

/**
 * What the browser posts the newsletter form to. Empty means "same origin",
 * which is what production uses: the reverse proxy forwards /api to FastAPI, so
 * no API hostname ends up in the page.
 */
export const publicApiBase: string = raw('PUBLIC_API_BASE_URL').replace(/\/$/, '');

/** Canonical origin, used for canonical links, Open Graph URLs and the sitemap. */
export const siteUrl: string = readUrl('PUBLIC_SITE_URL', 'https://girisimcilikvakfi.org');

/** How long a rendered page may be reused before the API is asked again, in seconds. */
export const pageCacheSeconds: number = readInt('PAGE_CACHE_SECONDS', 30);

/** What the browser is allowed to cache the HTML for, in seconds. */
export const browserCacheSeconds: number = readInt('BROWSER_CACHE_SECONDS', 30);

function readUrl(name: string, fallback: string): string {
  const value = raw(name) || fallback;
  try {
    new URL(value);
  } catch {
    throw new Error(`${name} must be an absolute URL, got ${JSON.stringify(value)}`);
  }
  return value.replace(/\/$/, '');
}

function readInt(name: string, fallback: number): number {
  const value = raw(name);
  if (!value) return fallback;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`${name} must be a whole number of seconds, got ${JSON.stringify(value)}`);
  }
  return parsed;
}
