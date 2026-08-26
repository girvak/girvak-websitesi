/**
 * Module: src/lib/api.ts
 * Layer: Lib
 * Purpose: Read page content from FastAPI at request time, hold the parsed
 *          result for a few seconds so a burst of visitors costs one call, and
 *          keep serving the last good copy if the API stops answering.
 *
 * Called by: src/pages/*
 * Calls: src/lib/env.ts
 */

import { apiBaseUrl, pageCacheSeconds } from './env';
import type { AboutContent, FellowContent, HomeContent, PeopleContent } from './types';

interface Entry<T> {
  value: T;
  storedAt: number;
  etag?: string;
}

/** Per-process, per-path. Shorter than the API's own snapshot TTL by design. */
const cache = new Map<string, Entry<unknown>>();

const TIMEOUT_MS = 5000;

export async function getHomeContent(): Promise<HomeContent> {
  return read<HomeContent>('/v1/content/home');
}

export async function getAboutContent(): Promise<AboutContent> {
  return read<AboutContent>('/v1/content/about');
}

export async function getFellowContent(): Promise<FellowContent> {
  return read<FellowContent>('/v1/content/fellow');
}

export async function getPeople(): Promise<PeopleContent> {
  return read<PeopleContent>('/v1/content/people');
}

/**
 * Fetch one content path.
 *
 * Sends the stored ETag, so an unchanged page costs the API a 304 instead of a
 * re-serialisation. Throws only when there is nothing at all to render — the
 * page decides what an empty section looks like.
 */
async function read<T>(path: string): Promise<T> {
  const entry = cache.get(path) as Entry<T> | undefined;
  const fresh = entry && (Date.now() - entry.storedAt) / 1000 < pageCacheSeconds;
  if (fresh) return entry.value;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      headers: entry?.etag ? { 'If-None-Match': entry.etag } : undefined,
      signal: controller.signal,
    });

    if (response.status === 304 && entry) {
      cache.set(path, { ...entry, storedAt: Date.now() });
      return entry.value;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const value = (await response.json()) as T;
    cache.set(path, {
      value,
      storedAt: Date.now(),
      etag: response.headers.get('etag') ?? undefined,
    });
    return value;
  } catch (error) {
    if (entry) {
      // Stale beats blank: the API is down, the last good copy is not.
      console.warn(`[content] ${path} failed (${String(error)}) — serving the last copy`);
      return entry.value;
    }
    console.error(`[content] ${path} failed and nothing is cached (${String(error)})`);
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
