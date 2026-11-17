/**
 * Module: src/lib/links.ts
 * Layer: Lib
 * Purpose: One rule for where a link opens: a link off this site opens in a new
 *          tab, a link on it (relative, #hash, or an absolute URL to our own
 *          domain) stays in this one. mailto: and tel: are left alone. Links come
 *          from Airtable, so this is decided per value, not per component.
 *
 * Called by: src/components/*, src/pages/*
 * Calls: src/lib/env.ts
 */

import { siteUrl } from './env';

const bare = (host: string): string => host.toLowerCase().replace(/^www\./, '');
const ownHost = bare(new URL(siteUrl).host);

/** True for an http(s) URL on another host. */
export function isExternal(href: string | null | undefined): boolean {
  if (!href || !/^https?:\/\//i.test(href)) return false;
  try {
    return bare(new URL(href).host) !== ownHost;
  } catch {
    return false;
  }
}

/** Spread onto an <a>: `<a href={x} {...newTab(x)}>`. */
export function newTab(href: string | null | undefined): { target?: '_blank'; rel?: string } {
  return isExternal(href) ? { target: '_blank', rel: 'noopener noreferrer' } : {};
}
