// Fellow program dynamic updater (client-side).
// Updates belt contents for fellows/alumni/challengers using /api/content/people.

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

  function personName(p) {
    return [p.first, p.last].filter(Boolean).join(' ');
  }

  function linkedInHref(raw) {
    if (!raw) return undefined;
    const first = String(raw).trim().split(/\s+/)[0] || '';
    if (!first || first === '#') return undefined;
    if (/linkedin\.com\/?$/i.test(first.replace(/\/$/, ''))) return undefined;
    const href = /^https?:\/\//i.test(first) ? first : `https://${first.replace(/^\/+/, '')}`;
    return /linkedin\.com\/in\//i.test(href) ? href : undefined;
  }

  function fellowCardMarkup(p, tone) {
    const name = personName(p);
    const yearFront = p.year ? `<span class="fcard-year">${escapeHtml(p.year)}</span>` : '';
    const yearBack = p.year ? `<span class="fcard-back-year">${escapeHtml(p.year)}</span>` : '';

    const img = p.photo
      ? `<img src="${escapeHtml(p.photo)}" alt="${escapeHtml(name)}" loading="lazy" decoding="async" />`
      : '';

    const uni = p.university || p.company
      ? `<span class="fcard-uni">${escapeHtml(p.university || p.company)}</span>`
      : '';

    const dept = p.department ? `<span class="fcard-dept">${escapeHtml(p.department)}</span>` : '';

    const linkedin = linkedInHref(p.linkedin);
    const linkedinAttr = linkedin ? ` data-linkedin="${escapeHtml(linkedin)}"` : '';

    return (
      `<figure class="fcard ${escapeHtml(tone)}" tabindex="0"${linkedinAttr}>` +
      '<div class="fcard-inner">' +
      '<div class="fcard-front">' +
      yearFront +
      img +
      `<div class="fcard-band"><span class="fcard-frontname">${escapeHtml(name)}</span></div>` +
      '</div>' +
      '<div class="fcard-back">' +
      yearBack +
      '<div class="fcard-back-meta">' +
      `<span class="fcard-name">${escapeHtml(name)}</span>` +
      uni +
      dept +
      '</div>' +
      '</div>' +
      '</div>' +
      '</figure>'
    );
  }

  function updateFcardBelt(trackId, people, tone) {
    const track = document.getElementById(trackId);
    if (!track) return;
    if (!Array.isArray(people)) return;

    track.innerHTML = people.map((p) => fellowCardMarkup(p, tone)).join('');
  }

  function challengerCardMarkup(p) {
    const name = personName(p);
    const year = p.year ? `<span class="cchcard-year">${escapeHtml(p.year)}</span>` : '';
    const uniVal = p.university || p.company;
    const uni = uniVal ? `<span class="cchcard-uni">${escapeHtml(uniVal)}</span>` : '';
    const dept = p.department ? `<span class="cchcard-dept">${escapeHtml(p.department)}</span>` : '';

    const linkedin = linkedInHref(p.linkedin);
    const linkedinAttr = linkedin ? ` data-linkedin="${escapeHtml(linkedin)}"` : '';

    return (
      `<figure class="cchcard"${linkedinAttr}>` +
      `${year}` +
      `<span class="cchcard-name">${escapeHtml(name)}</span>` +
      `${uni}` +
      `${dept}` +
      `</figure>`
    );
  }

  function updateChallengerBelt(trackId, people) {
    const track = document.getElementById(trackId);
    if (!track) return;
    if (!Array.isArray(people)) return;
    track.innerHTML = people.map((p) => challengerCardMarkup(p)).join('');
  }

  async function updateFellowProgram() {
    const resp = await fetch('/api/content/people', {
      method: 'GET',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    });
    if (!resp.ok) return;
    const people = await resp.json();

    const fellows = Array.isArray(people?.fellows) ? people.fellows : [];
    const alumni = Array.isArray(people?.alumni) ? people.alumni : [];
    const challengers = Array.isArray(people?.challengers) ? people.challengers : [];

    updateFcardBelt('belt', fellows, 'fc-fellow');
    updateFcardBelt('abelt', alumni, 'fc-alumni');
    updateChallengerBelt('cbelt', challengers);
  }

  window.__girvakUpdateFellowProgram = updateFellowProgram;

  updateFellowProgram().catch(() => {});
  setInterval(() => updateFellowProgram().catch(() => {}), POLL_MS);
})();

