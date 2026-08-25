// Partners dynamic updater (client-side).
// Fetches the latest /api/content/home and updates #partners logos/headline
// without requiring a frontend rebuild.

import { safeHref, safeImageSrc } from '../lib/urls.ts';

(function () {
  // Dev-only. In production the site is fully static: these updaters would
  // overwrite Astro's optimized responsive images with raw backend URLs, and
  // would make the API a hard runtime dependency of every page. Content
  // changes reach production through a rebuild instead.
  if (!import.meta.env.DEV) return;
  const root = document.getElementById('partners');
  if (!root) return;

  const POLL_MS = 10 * 60 * 1000; // 10 minutes

  function escapeHtml(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function updatePartners() {
    const resp = await fetch('/api/content/home', {
      method: 'GET',
      cache: 'no-store',
      headers: { 'Accept': 'application/json' },
    });
    if (!resp.ok) return;

    const data = await resp.json();
    const partners = data?.partners;
    if (!partners) return;

    // Headline
    const h2 = root.querySelector('.partners-copy h2');
    if (h2) {
      const pre = partners.headline_pre ?? '';
      const highlight = partners.headline_highlight ?? '';
      h2.innerHTML = `${escapeHtml(pre)}<span style="color:#f76b52">${escapeHtml(highlight)}</span>`;
    }

    // Featured logo
    if (partners.featured) {
      const featA = root.querySelector('a.partners-feat');
      const featImg = featA ? featA.querySelector('img') : null;
      if (featA && featImg) {
        featA.href = safeHref(partners.featured.href, '#');
        featA.setAttribute('aria-label', partners.featured.name ?? '');
        featImg.src = safeImageSrc(partners.featured.logo, '');
        featImg.alt = partners.featured.name ?? '';
      }
    }

    // Grid logos
    const grid = root.querySelector('.plogo-grid');
    if (grid && Array.isArray(partners.logos)) {
      grid.innerHTML = partners.logos
        .map((p) => {
          const href = safeHref(p.href, '#');
          const name = p.name ?? '';
          const logo = safeImageSrc(p.logo, '');
          return (
            `<a href="${escapeHtml(href)}" class="plogo" aria-label="${escapeHtml(name)}">` +
            `<img src="${escapeHtml(logo)}" alt="${escapeHtml(name)}" loading="lazy" decoding="async" />` +
            `</a>`
          );
        })
        .join('');
    }
  }

  // Expose for the UI refresh button.
  window.__girvakUpdatePartners = updatePartners;

  // Initial update
  updatePartners().catch(() => {});

  // Periodic updates while the user keeps the tab open.
  setInterval(() => {
    updatePartners().catch(() => {});
  }, POLL_MS);
})();

