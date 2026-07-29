import type { AboutContent, FellowContent, HomeContent, PeopleContent } from './types';
import fallback from '../data/home_content.json';
import aboutFallback from '../data/about_content.json';
import fellowFallback from '../data/fellow_content.json';

// Fetched at BUILD time (SSG). The FastAPI backend is the source of truth;
// if it's unreachable during a build, we fall back to the bundled snapshot so
// the site still builds and renders.
const API_BASE = import.meta.env.API_BASE_URL ?? 'http://localhost:8000';

export async function getHomeContent(): Promise<HomeContent> {
  try {
    const res = await fetch(`${API_BASE}/api/content/home`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as HomeContent;
  } catch (err) {
    console.warn(
      `[content] Could not reach ${API_BASE}/api/content/home — using bundled fallback. (${err})`,
    );
    return fallback as HomeContent;
  }
}

// Fetched at BUILD time. Returns null if the backend is unreachable OR Airtable
// is off (empty lists) — callers then keep their bundled fallback people.
export async function getPeople(): Promise<PeopleContent | null> {
  try {
    const res = await fetch(`${API_BASE}/api/content/people`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as PeopleContent;
    const total =
      data.trustees.length +
      data.directors.length +
      data.team.length +
      data.fellows.length +
      (data.alumni?.length ?? 0) +
      (data.challengers?.length ?? 0);
    return total > 0 ? data : null;
  } catch (err) {
    console.warn(
      `[content] Could not reach ${API_BASE}/api/content/people — using bundled fallback people. (${err})`,
    );
    return null;
  }
}

export async function getAboutContent(): Promise<AboutContent> {
  try {
    const res = await fetch(`${API_BASE}/api/content/about`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as AboutContent;
  } catch (err) {
    console.warn(
      `[content] Could not reach ${API_BASE}/api/content/about — using bundled fallback. (${err})`,
    );
    return aboutFallback as AboutContent;
  }
}

export async function getFellowContent(): Promise<FellowContent> {
  try {
    const res = await fetch(`${API_BASE}/api/content/fellow`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as FellowContent;
  } catch (err) {
    console.warn(
      `[content] Could not reach ${API_BASE}/api/content/fellow — using bundled fallback. (${err})`,
    );
    return fellowFallback as FellowContent;
  }
}
