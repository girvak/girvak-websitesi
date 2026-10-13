// ============================================================
// GİRVAK Programs (/programs) — tiles, panels, filters.
//
// Ported from the design project's programs.js and the page's inline script.
// The design built its cards here from a hard-coded array; this page is
// server-rendered from Airtable, so the cards and dropdowns are already in the
// HTML and the script only toggles them.
//
// - A tile opens its panel under the row (one at a time) and scrolls to it;
//   the same tile closes it. `/programs#<slug>` opens one on arrival, and so
//   does a menu link to it while already on the page.
// - Each panel filters on its own, with the shared filter bar
//   (filters-multi.js): several values in one dropdown widen, different
//   dropdowns narrow, and a dropdown only offers what would still return a card.
// - A card's hover fill alternates coral and turquoise, as in the design.
// ============================================================
import { fold, hits, pruneOptions, wire, wireSearch } from './filters-multi.js';

const DIMS = ['sectors', 'targets', 'stages', 'status'];
const HOVERS = ['#F76C53', '#19BAD1'];
// Below the fixed header, so the filter bar is not tucked under it.
const SCROLL_OFFSET = 120;

const tiles = [...document.querySelectorAll('.pp-cat[aria-controls]')];
const panelOf = (tile) => document.getElementById(tile.getAttribute('aria-controls'));
const calm = window.matchMedia('(prefers-reduced-motion: reduce)');

function close(tile) {
  const panel = panelOf(tile);
  tile.setAttribute('aria-expanded', 'false');
  tile.classList.remove('is-open');
  if (panel) { panel.classList.remove('is-open'); panel.hidden = true; }
}

function open(tile, { scroll = true } = {}) {
  tiles.forEach((other) => { if (other !== tile) close(other); });
  const panel = panelOf(tile);
  if (!panel) return;
  tile.setAttribute('aria-expanded', 'true');
  tile.classList.add('is-open');
  panel.hidden = false;
  void panel.offsetHeight; // let the panel lay out before it fades in
  panel.classList.add('is-open');
  if (!scroll) return;
  requestAnimationFrame(() => {
    const anchor = panel.querySelector('.fv-filters') || panel;
    const y = anchor.getBoundingClientRect().top + window.scrollY - SCROLL_OFFSET;
    window.scrollTo({ top: y, behavior: calm.matches ? 'auto' : 'smooth' });
  });
}

tiles.forEach((tile) => {
  tile.addEventListener('click', () => {
    if (tile.getAttribute('aria-expanded') === 'true') close(tile);
    else open(tile);
  });
});

/**
 * Open the tile the address names, if any. The tile's id is `tile-<slug>`, not
 * the slug, so the browser does not jump to and focus it on its own.
 */
function fromHash() {
  const slug = decodeURIComponent(location.hash.slice(1));
  const tile = slug && tiles.find((t) => t.dataset.slug === slug);
  if (tile) open(tile);
}
fromHash();
window.addEventListener('hashchange', fromHash);

// ---------- one panel's filters ----------
document.querySelectorAll('[data-pp-panel]').forEach((panel) => {
  const scope = `#${CSS.escape(panel.id)}`;
  const cards = [...panel.querySelectorAll('.pp-card')];
  const empty = panel.querySelector('.pp-empty');
  const reset = panel.querySelector('[data-pp-reset]');
  const state = { q: '', sectors: [], targets: [], stages: [], status: [] };

  cards.forEach((card, i) => {
    card.dataset.q = fold(card.textContent);
    card.style.setProperty('--pp-accent', HOVERS[i % 2]);
  });
  let hoverIdx = 0;
  cards.forEach((card) => card.addEventListener('mouseenter', () => {
    card.style.setProperty('--pp-accent', HOVERS[hoverIdx++ % 2]);
  }));

  function passes(card, skip) {
    if (state.q && (card.dataset.q || '').indexOf(state.q) === -1) return false;
    return DIMS.every((key) => key === skip || hits(card.dataset[key], state[key], ';'));
  }

  function apply() {
    let shown = 0;
    cards.forEach((card) => {
      const ok = passes(card);
      card.hidden = !ok;
      if (ok) shown += 1;
    });
    if (empty) empty.hidden = shown > 0;
    pruneOptions({
      items: cards,
      dims: DIMS,
      passes,
      valuesOf: (card, key) => (card.dataset[key] || '').split(';').filter(Boolean),
      scopeFor: (key) => panel.querySelector(`.fv-filter[data-key="${key}"]`),
      state,
    });
    if (reset) reset.classList.toggle('is-live', !!state.q || filters.live());
  }

  const filters = wire(`${scope} .fv-filter:not(.ca-search)`, state, apply);
  const search = wireSearch(`${scope} .ca-search`, panel.querySelector('[data-pp-search]'), (query) => {
    state.q = query;
    apply();
  });

  reset?.addEventListener('click', () => {
    state.q = '';
    search.clear();
    filters.reset();
    apply();
  });

  apply();
});
