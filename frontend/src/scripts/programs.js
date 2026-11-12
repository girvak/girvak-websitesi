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
import { scrollToTop } from './scroll-to.js';

const DIMS = ['programs', 'sectors', 'targets', 'stages', 'status'];
const HOVERS = ['#F76C53', '#19BAD1'];

const tiles = [...document.querySelectorAll('.pp-cat[aria-controls]')];

// The page has one panel with every program; a tile only sets its `programs`
// filter. The panel's setup (below) fills this in.
let panelApi = { setCategory(_name) {} };
const panel = document.getElementById('panel-all');

function closeAll() {
  tiles.forEach((t) => { t.setAttribute('aria-expanded', 'false'); t.classList.remove('is-open'); });
  if (panel) { panel.classList.remove('is-open'); panel.hidden = true; }
  panelApi.setCategory(null);
}

function open(tile, { scroll = true } = {}) {
  if (!panel) return;
  tiles.forEach((t) => {
    const on = t === tile;
    t.setAttribute('aria-expanded', on ? 'true' : 'false');
    t.classList.toggle('is-open', on);
  });
  panel.hidden = false;
  void panel.offsetHeight; // let the panel lay out before it fades in
  panel.classList.add('is-open');
  panelApi.setCategory(tile.dataset.name || null);
  if (!scroll) return;
  // The panel's top (its filter bar) under the nav; scrollToTop re-checks once
  // the panel has finished sliding in from -8px.
  requestAnimationFrame(() => scrollToTop(panel));
}

tiles.forEach((tile) => {
  tile.addEventListener('click', () => {
    if (tile.getAttribute('aria-expanded') === 'true') closeAll();
    else {
      open(tile);
      // Keep the address bar in sync so a shared link reopens this category.
      const slug = tile.dataset.slug;
      if (slug) {
        const next = `#${slug}`;
        if (location.hash !== next) history.replaceState(null, '', next);
      }
    }
  });
});

/**
 * The tile a name points at: its exact slug, or a short alias the links use
 * (`talent`, `development`, `entrepreneur`), matched on the start of the slug.
 * @param {string} name
 */
function tileFor(name) {
  const want = name.toLowerCase();
  if (!want) return undefined;
  return tiles.find((t) => t.dataset.slug === want) || tiles.find((t) => (t.dataset.slug || '').startsWith(want));
}

/**
 * Open the tile the address names — `/programs#talent-programs`,
 * `/programs?category=talent` — if any. The tile's id is `tile-<slug>`, not
 * the slug, so the browser does not jump to and focus it on its own.
 */
function fromHash() {
  const named = decodeURIComponent(location.hash.slice(1)) || new URLSearchParams(location.search).get('category') || '';
  const tile = tileFor(named);
  if (tile) open(tile);
}
// ---------- one panel's filters ----------
document.querySelectorAll('[data-pp-panel]').forEach((panel) => {
  const scope = `#${CSS.escape(panel.id)}`;
  const cards = [...panel.querySelectorAll('.pp-card')];
  const empty = panel.querySelector('.pp-empty');
  const reset = panel.querySelector('[data-pp-reset]');
  const state = { q: '', programs: [], sectors: [], targets: [], stages: [], status: [] };

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

  // A tile sets (or clears) the `programs` filter, then the list repaints.
  panelApi = {
    setCategory(name) {
      filters.set('programs', name ? [name] : []);
      apply();
    },
  };

  apply();
});

// Last, so the panel's filters exist when a link names a category.
fromHash();
window.addEventListener('hashchange', fromHash);
