// Pull every CMS image into the frontend as a BUILD ASSET, before `astro build`.
//
// Why this exists: the backend mirrors Airtable attachments (their own URLs
// expire) and serves them from /media. That works, but it puts a Python process
// in the hot path for every image byte — no CDN, no responsive variants, and the
// site stops rendering images whenever the API is down. A 3000px photo also
// reaches the visitor untouched: `/board-of-trustees` cost 262 MB to scroll.
//
// So we copy the images in at build time instead:
//   raster -> src/assets/images/cms/  (Astro emits hashed, responsive .webp)
//   svg    -> public/media/           (vector; nothing to optimise, served as-is
//                                      under the same /media/... path)
//
// After this runs, the built HTML references /_astro/*.webp and /media/*.svg —
// nothing points at the backend, so the static host serves every image.
//
// Failure is non-fatal: an unreachable backend leaves the previous sync in
// place and the build continues, same as lib/content.ts falling back to its
// bundled snapshot.

import { mkdir, readdir, unlink, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const RASTER_DIR = join(ROOT, 'src/assets/images/cms');
const SVG_DIR = join(ROOT, 'public/media');
const API_BASE = process.env.API_BASE_URL || 'http://127.0.0.1:8000';
const ENDPOINTS = ['home', 'about', 'fellow', 'people'];

const isSvg = (name) => name.toLowerCase().endsWith('.svg');

/** Every "/media/..." string anywhere in a content payload. */
function collectMediaPaths(node, out = new Set()) {
  if (typeof node === 'string') {
    if (node.startsWith('/media/')) out.add(node);
  } else if (Array.isArray(node)) {
    for (const item of node) collectMediaPaths(item, out);
  } else if (node && typeof node === 'object') {
    for (const value of Object.values(node)) collectMediaPaths(value, out);
  }
  return out;
}

async function fetchContent() {
  const paths = new Set();
  for (const ep of ENDPOINTS) {
    const res = await fetch(`${API_BASE}/api/content/${ep}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`${ep}: HTTP ${res.status}`);
    collectMediaPaths(await res.json(), paths);
  }
  return paths;
}

/** Remove files this sync no longer references, so the dir can't grow forever. */
async function prune(dir, keep) {
  if (!existsSync(dir)) return 0;
  let removed = 0;
  for (const name of await readdir(dir)) {
    if (!keep.has(name)) {
      await unlink(join(dir, name));
      removed += 1;
    }
  }
  return removed;
}

let paths;
try {
  paths = await fetchContent();
} catch (err) {
  console.warn(`[cms-media] ${API_BASE} unreachable — keeping the previous sync. (${err})`);
  process.exit(0);
}

await mkdir(RASTER_DIR, { recursive: true });
await mkdir(SVG_DIR, { recursive: true });

const wantRaster = new Set();
const wantSvg = new Set();
let downloaded = 0;
let bytes = 0;

for (const path of paths) {
  const name = path.split('/').pop();
  if (!name) continue;
  const svg = isSvg(name);
  (svg ? wantSvg : wantRaster).add(name);

  const dest = join(svg ? SVG_DIR : RASTER_DIR, name);
  // Names are content-addressed by Airtable attachment id, so an existing file
  // is always the right file — replacing an image in Airtable mints a new id.
  if (existsSync(dest)) continue;

  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    console.warn(`[cms-media] skipped ${path} — HTTP ${res.status}`);
    continue;
  }
  const buf = Buffer.from(await res.arrayBuffer());
  await writeFile(dest, buf);
  downloaded += 1;
  bytes += buf.length;
}

const prunedRaster = await prune(RASTER_DIR, wantRaster);
const prunedSvg = await prune(SVG_DIR, wantSvg);

console.log(
  `[cms-media] ${wantRaster.size} raster + ${wantSvg.size} svg in sync ` +
    `(${downloaded} downloaded, ${(bytes / 1024 / 1024).toFixed(1)} MB; ` +
    `${prunedRaster + prunedSvg} stale removed)`,
);
