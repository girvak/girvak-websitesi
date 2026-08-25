/** Safe URL helpers — defense-in-depth for CMS-provided links and images. */

const ALLOWED_HREF_SCHEMES = new Set(['http', 'https', 'mailto', 'tel']);
const ALLOWED_IMAGE_SCHEMES = new Set(['http', 'https']);

export function safeHref(url: string | null | undefined, fallback = '#'): string {
  const value = String(url ?? '').trim();
  if (!value) return fallback;
  if (value.startsWith('#') || value.startsWith('/')) return value;
  try {
    const parsed = new URL(value);
    if (!ALLOWED_HREF_SCHEMES.has(parsed.protocol.replace(':', ''))) return fallback;
    return value;
  } catch {
    return fallback;
  }
}

export function safeImageSrc(url: string | null | undefined, fallback = ''): string {
  const value = String(url ?? '').trim();
  if (!value) return fallback;
  if (value.startsWith('/')) return value;
  try {
    const parsed = new URL(value);
    if (!ALLOWED_IMAGE_SCHEMES.has(parsed.protocol.replace(':', ''))) return fallback;
    return value;
  } catch {
    return fallback;
  }
}
