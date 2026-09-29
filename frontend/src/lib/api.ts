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
import type {
  AboutContent,
  FellowContent,
  HomeContent,
  PeopleContent,
  FounderCard,
  Venture,
  VenturesContent,
} from './types';

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
 * Both tabs of the founders & ventures directory, whole.
 *
 * The page filters client-side — the design flips between a founders tab and a
 * ventures tab over one grid — so every card has to be in the HTML. The API
 * paginates each tab separately (a few dozen ventures against a few hundred
 * founders), so this walks both rather than asking for an unbounded list.
 */
export async function getVentures(): Promise<VenturesContent> {
  const [ventures, founders] = await Promise.all([
    walk<Venture>('ventures', (payload) => payload.items),
    walk<FounderCard>('founders', (payload) => payload.founders),
  ]);
  return { ...ventures.first, items: ventures.all, founders: founders.all };
}

/** Read one tab page by page, collecting the list the caller names. */
async function walk<T>(
  kind: 'ventures' | 'founders',
  pick: (payload: VenturesContent) => T[],
): Promise<{ first: VenturesContent; all: T[] }> {
  const path = `/v1/content/ventures?kind=${kind}&per_page=${VENTURES_PER_PAGE}`;
  const first = await read<VenturesContent>(path);
  const all: T[] = [...pick(first)];
  for (let page = 2; page <= first.page.total_pages; page += 1) {
    all.push(...pick(await read<VenturesContent>(`${path}&page=${page}`)));
  }
  return { first, all };
}

/** The API's own ceiling. Asking for more is silently reduced to this. */
const VENTURES_PER_PAGE = 48;

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
