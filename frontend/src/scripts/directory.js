// ============================================================
// GİRVAK All Fellows / All Alumni — filters, search, "load more", flip cards
//
// Ported from the design project's fellows-all.js and alumni-all.js, which are
// the same script. The design kept its people in a hard-coded array and built the
// cards and dropdowns here; these pages are server-rendered from the Airtable
// `people` table, so both already exist in the HTML and the script only toggles
// `hidden`.
//
// The design shows everyone at once. With a few hundred portraits that is tens
// of megabytes as the visitor scrolls, so 24 are revealed at a time and a card
// that is `hidden` never fetches its photo. Filters and search run over the
// whole list, not the revealed part.
// ============================================================
import { fold, hits, pruneOptions, wire, wireSearch } from './filters-multi.js';
import { PAGE_SIZE, initLoadMore, paginate } from './load-more.js';
import { buildSearch, parseFilters, visibleCount } from './pager.js';
import './hero-letters.js';

const grid = document.getElementById('faGrid');

if (grid) {
  const cards = [...grid.querySelectorAll('.fv-card')];
  const empty = document.getElementById('faEmpty');
  const reset = document.getElementById('faReset');
  const state = { q: '', university: [], department: [], year: [] };

  // Search runs over the card's own text, folded so "ayse" finds "Ayşe". Built
  // once — the cards never change.
  cards.forEach((c) => { c.dataset.q = fold(c.textContent); });

  // The three dropdown dimensions. Each card carries exactly one value per
  // dimension, so nothing is split.
  const DIMS = ['university', 'department', 'year'];

  /** Does a card pass every dimension except, optionally, one of them? */
  function passes(c, skip) {
    if (state.q && (c.dataset.q || '').indexOf(state.q) === -1) return false;
    return DIMS.every((key) => key === skip || hits(c.dataset[key], state[key]));
  }

  /** Narrow each dropdown to the choices that would actually return a card. */
  function refreshOptions() {
    pruneOptions({
      items: cards,
      dims: DIMS,
      passes,
      valuesOf: (c, key) => (c.dataset[key] ? [c.dataset[key]] : []),
      scopeFor: (key) => document.querySelector(`.fa .fv-filter[data-key="${key}"]`),
      state,
    });
  }

  // How many the visitor has asked to see, the total that match, and the search
  // text as typed (the URL keeps that, not the folded form).
  let shown = PAGE_SIZE;
  let matched = 0;
  let rawQuery = '';

  /** Paint the current filter and reveal. `animateFrom` is set by "load more". */
  function render(animateFrom = -1) {
    matched = paginate(cards, passes, shown, animateFrom);
    if (empty) empty.hidden = matched > 0;
    refreshOptions();
    if (reset) reset.classList.toggle('is-live', !!state.q || filters.live());
    more.update(matched, shown);
  }

  /** A filter or the search changed: start again from the first 24. */
  function apply() {
    shown = PAGE_SIZE;
    render();
    // The same view is the same URL, so a link can be shared. Replaced, not
    // pushed: each dropdown click is not a page the back button should visit.
    history.replaceState(null, '', location.pathname + buildSearch(rawQuery, state, DIMS) + location.hash);
  }

  const more = initLoadMore({
    button: document.getElementById('faMoreBtn'),
    status: document.getElementById('faStatus'),
    noun: document.getElementById('faMore')?.dataset.noun || 'people',
    onMore() {
      const from = visibleCount(matched, shown);
      shown += PAGE_SIZE;
      render(from);
    },
  });

  // One accent — the page's own colour — where the other pages alternate two.
  const accent = getComputedStyle(grid).getPropertyValue('--fellow').trim() || '#281858';
  const filters = wire('.fa .fv-filter:not(.ca-search)', state, apply, [accent]);

  const searchBox = wireSearch('.fa .ca-search', document.getElementById('faSearch'), (query, raw) => {
    state.q = query;
    rawQuery = raw;
    apply();
  });

  if (reset) {
    reset.addEventListener('click', () => {
      state.q = '';
      rawQuery = '';
      searchBox.clear();
      filters.reset();
      apply();
    });
  }

  // ---------- flip motion: staggered, random axis ----------
  const AXES = [
    ['rotateY(180deg)', 'rotateY(180deg)'],
    ['rotateY(-180deg)', 'rotateY(-180deg)'],
    ['rotateX(180deg)', 'rotateX(180deg)'],
    ['rotateX(-180deg)', 'rotateX(-180deg)'],
  ];
  function roll(c) {
    const a = AXES[Math.floor(Math.random() * AXES.length)];
    c.style.setProperty('--rot', a[0]);
    c.style.setProperty('--brot', a[1]);
    c.style.setProperty('--fd', `${Math.round(Math.random() * 130)}ms`);
  }
  // Rolled once up front and again as the pointer arrives — never on focus.
  // Clicking a card focuses it, and re-rolling then changed the axis halfway
  // through the flip, which read as a glitch rather than a flourish.
  cards.forEach((c) => {
    roll(c);
    c.addEventListener('mouseenter', () => roll(c));
  });

  // ---------- a shared link opens the view it was copied from ----------
  const initial = parseFilters(location.search, DIMS);
  DIMS.forEach((key) => filters.set(key, initial.values[key]));
  if (initial.q) {
    rawQuery = initial.q;
    state.q = searchBox.set(initial.q);
  }

  apply();
}
