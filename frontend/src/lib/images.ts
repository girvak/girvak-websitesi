import type { ImageMetadata } from 'astro';

// Eagerly map every optimizable photo under src/assets/images so we can resolve
// the web-style paths stored in content (e.g. "/images/hero-1.jpg") to a
// bundled, optimizable asset. Returns undefined for images not bundled (those
// fall back to a plain <img> from /public).
const modules = import.meta.glob<{ default: ImageMetadata }>(
  '/src/assets/images/**/*.{jpg,jpeg,png,webp,avif,JPG,PNG}',
  { eager: true },
);

export function resolveImage(contentPath: string): ImageMetadata | undefined {
  const file = contentPath.split('/').pop();
  if (!file) return undefined;
  return modules[`/src/assets/images/${file}`]?.default;
}
