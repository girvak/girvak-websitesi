import type { ImageMetadata } from 'astro';

// Every optimizable photo under src/assets/images — including the CMS images
// that scripts/sync-cms-media.mjs downloads into cms/ before each build. Astro
// turns these into hashed, responsive .webp files served by the static host.
const modules = import.meta.glob<{ default: ImageMetadata }>(
  '/src/assets/images/**/*.{jpg,jpeg,png,webp,avif,JPG,PNG}',
  { eager: true },
);

// Content stores web-style paths ("/images/hero-1.jpg", "/media/attXY_large.jpg")
// that say nothing about where the file sits in src/assets/images. Index by
// basename so assets can live in subdirectories.
const byBasename = new Map<string, ImageMetadata>();
for (const [path, mod] of Object.entries(modules)) {
  const file = path.split('/').pop();
  if (file) byBasename.set(file, mod.default);
}

export function resolveImage(contentPath: string): ImageMetadata | undefined {
  // Absolute URLs are somebody else's asset — never match them against ours,
  // or a remote "logo.png" would silently render a bundled "logo.png".
  if (/^https?:\/\//i.test(contentPath)) return undefined;
  const file = contentPath.split('/').pop();
  return file ? byBasename.get(file) : undefined;
}

// True when we have no bundled asset for this src, so the caller must emit a
// plain <img> and let the browser fetch the URL as-is. Covers absolute URLs and
// SVGs (vector — nothing for the raster pipeline to do; sync-cms-media.mjs puts
// them in public/media/ under their original /media/... path).
export function isUnbundled(src?: string): boolean {
  return !!src && !resolveImage(src);
}
