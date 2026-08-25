// Board of Trustees dynamic updater (client-side).
// Fetches /api/content/about + /api/content/people and replaces:
// - hero title/subtitle
// - trustees grid HTML

(function () {
  // Dev-only. In production the site is fully static: these updaters would
  // overwrite Astro's optimized responsive images with raw backend URLs, and
  // would make the API a hard runtime dependency of every page. Content
  // changes reach production through a rebuild instead.
  if (!import.meta.env.DEV) return;
  const POLL_MS = 10 * 60 * 1000; // 10 minutes

  function escapeHtml(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function initials(first, last) {
    const fi = String(first ?? '').charAt(0).toUpperCase();
    const la = String(last ?? '').charAt(0).toUpperCase();
    return `${fi}${la}`.trim();
  }

  function linkedInHref(raw) {
    if (!raw) return undefined;
    const first = String(raw).trim().split(/\s+/)[0] || '';
    if (!first || first === '#') return undefined;
    if (/linkedin\.com\/?$/i.test(first.replace(/\/$/, ''))) return undefined;
    const href = /^https?:\/\//i.test(first) ? first : `https://${first.replace(/^\/+/, '')}`;
    return /linkedin\.com\/in\//i.test(href) ? href : undefined;
  }

  function updateGrid(container, people) {
    const BOARD_COLORS = ['#19BAD1', '#F76C53', '#373D42'];
    const forceColor = '#373D42';

    if (!container) return;
    if (!Array.isArray(people)) return;

    // keep deterministic order: first name + last name alpha
    const sorted = [...people].sort((a, b) => {
      const an = `${a.first ?? ''} ${a.last ?? ''}`.trim().toLowerCase();
      const bn = `${b.first ?? ''} ${b.last ?? ''}`.trim().toLowerCase();
      return an.localeCompare(bn);
    });

    container.innerHTML = sorted
      .map((p, i) => {
        const name = `${p.first ?? ''} ${p.last ?? ''}`.trim();
        const href = linkedInHref(p.linkedin);
        const Tag = href ? 'a' : 'div';

        const photo = p.photo ?? '';
        const hasPhoto = !!photo;
        const col = forceColor;

        let photoHtml = '';
        if (hasPhoto) {
          const src = String(photo);
          photoHtml = `<img class="bcard-photo" src="${escapeHtml(src)}" alt="${escapeHtml(name)}" width="260" height="278" loading="lazy" decoding="async" />`;
        } else {
          photoHtml = `<span class="bcard-initials">${escapeHtml(initials(p.first, p.last))}</span>`;
        }

        const company = p.company ? `<span class="bcard-company">${escapeHtml(p.company)}</span>` : '';
        const position = p.position ? `<span class="bcard-position">${escapeHtml(p.position)}</span>` : '';

        const baseAttrs = `class="bcard" style="--bc:${col}"`;
        if (Tag === 'a') {
          return `<a ${baseAttrs} href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${photoHtml}<div class="bcard-band"><span class="bcard-name">${escapeHtml(name)}</span>${company}${position}</div></a>`;
        }
        return `<div ${baseAttrs} role="group" tabindex="0">${photoHtml}<div class="bcard-band"><span class="bcard-name">${escapeHtml(name)}</span>${company}${position}</div></div>`;
      })
      .join('');
  }

  async function updateBoardTrustees() {
    const aboutResp = await fetch('/api/content/about', { method: 'GET', cache: 'no-store', headers: { Accept: 'application/json' } });
    if (!aboutResp.ok) return;
    const about = await aboutResp.json();

    const peopleResp = await fetch('/api/content/people', { method: 'GET', cache: 'no-store', headers: { Accept: 'application/json' } });
    if (!peopleResp.ok) return;
    const people = await peopleResp.json();

    // hero
    const h1 = document.querySelector('.ab-hero--home h1.ab-hero-title--page');
    const sub = document.querySelector('.ab-hero--home .ab-hero-sub');
    if (h1 && about?.trustees) h1.textContent = about.trustees.headline ?? '';
    if (sub && about?.trustees) sub.textContent = about.trustees.subheadline ?? '';

    // grid
    const grid = document.getElementById('trustees-grid-full');
    updateGrid(grid, people?.trustees ?? []);
  }

  // Expose for the UI refresh button.
  window.__girvakUpdateBoardTrustees = updateBoardTrustees;

  updateBoardTrustees().catch(() => {});
  setInterval(() => updateBoardTrustees().catch(() => {}), POLL_MS);
})();

