// ============================================================
// GİRVAK Founders & Ventures — tabs, filters, flip cards
//
// Ported from the design project's fv.js. Two changes:
//  - it imports the filter mechanic instead of reading a `GVF` global;
//  - cards carry slugs (`ag-tech-food-tech`) rather than display labels, so a
//    filter never depends on how an editor punctuated a sector name.
//
// Every card for both tabs is in the HTML; the server rendered them. Switching
// tabs and filtering only toggles `hidden`, so nothing is re-fetched.
// ============================================================
import { fold, hits, pruneOptions, wire, wireSearch } from './filters-multi.js';
import { parseFilters } from './pager.js';
import './hero-letters.js';

const grid = document.getElementById('fvGrid');

if (grid) {
  const cards = [...grid.querySelectorAll('.fv-card')];
  const empty = document.getElementById('fvEmpty');

  const state = { kind: 'founders', q: '', sector: [], program: [], year: [] };

  // Search runs over the card's own text, folded so "ayse" finds "Ayşe". Built
  // once — the cards never change.
  cards.forEach((c) => { c.dataset.q = fold(c.textContent); });

  // The three dropdown dimensions. A card can sit in several sectors or
  // programmes at once — those arrive `;`-joined — while a cohort is one value.
  const DIMS = [
    { key: 'sector', split: ';' },
    { key: 'program', split: ';' },
    { key: 'year', split: null },
  ];

  /** Does a card pass every dimension except, optionally, one of them? */
  function passes(c, skip) {
    if (c.dataset.kind !== state.kind) return false;
    if (state.q && (c.dataset.q || '').indexOf(state.q) === -1) return false;
    return DIMS.every(
      (d) => d.key === skip || hits(c.dataset[d.key], state[d.key], d.split || undefined),
    );
  }

  /** The values a card carries for one dimension. */
  function valuesOf(c, dim) {
    const raw = c.dataset[dim.key] || '';
    if (!raw) return [];
    return dim.split ? raw.split(dim.split).map((v) => v.trim()).filter(Boolean) : [raw];
  }

  /** Narrow each dropdown to the choices that would actually return a card. */
  function refreshOptions() {
    pruneOptions({
      items: cards,
      dims: DIMS.map((d) => d.key),
      passes,
      valuesOf: (c, key) => valuesOf(c, DIMS.find((d) => d.key === key)),
      scopeFor: (key) => document.querySelector(`.fv-filter[data-key="${key}"]`),
      state,
    });
  }

  function apply() {
    let shown = 0;
    cards.forEach((c) => {
      const ok = passes(c);
      c.hidden = !ok;
      if (ok) shown += 1;
    });
    if (empty) empty.hidden = shown > 0;
    refreshOptions();
    const rs = document.getElementById('fvReset');
    if (rs) rs.classList.toggle('is-live', !!state.q || multi.live());
  }

  // ---------- tabs ----------
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const FADE_MS = 170;
  // Past this many cards the stagger stops growing, so the ventures tab and a
  // several-hundred-card founders tab settle in the same beat instead of one
  // taking four seconds.
  const STAGGER_CAP = 20;

  /** Number the visible cards so CSS can stagger them, then restart the run. */
  function enter() {
    let i = 0;
    cards.forEach((c) => {
      if (c.hidden) return;
      c.style.setProperty('--i', Math.min(i, STAGGER_CAP));
      i += 1;
    });
    grid.classList.remove('is-entering');
    void grid.offsetWidth; // reflow, or the animation would not replay
    grid.classList.add('is-entering');
  }

  /** Fade the outgoing set away, swap, then rise the arriving one in. */
  function swapTo(kind) {
    if (kind === state.kind) return;
    if (reduceMotion) {
      state.kind = kind;
      apply();
      return;
    }
    grid.classList.add('is-swapping');
    window.setTimeout(() => {
      state.kind = kind;
      apply();
      grid.classList.remove('is-swapping');
      enter();
    }, FADE_MS);
  }

  const tabFills = ['#19BAD1', '#F76C53'];
  let tabIdx = 0;
  let hoverIdx = 0;

  function activate(tab, animate) {
    tabIdx += 1;
    document.querySelectorAll('.fv-tabs').forEach((t) => {
      t.style.setProperty('--fv-tab-fill', tabFills[tabIdx % 2]);
    });
    document.querySelectorAll('.fv-tab').forEach((o) => {
      const on = o === tab;
      o.classList.toggle('is-on', on);
      o.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    if (animate) {
      swapTo(tab.dataset.tab);
    } else {
      state.kind = tab.dataset.tab;
      apply();
    }
  }

  document.querySelectorAll('.fv-tab').forEach((tab) => {
    tab.addEventListener('mouseenter', () => {
      hoverIdx += 1;
      tab.style.setProperty('--fv-tabhover-fill', tabFills[hoverIdx % 2]);
    });
    tab.addEventListener('click', () => activate(tab, true));
  });

  // ---------- filters ----------
  const multi = wire('.fv-filters .fv-filter:not(.ca-search)', state, apply, tabFills);

  const searchBox = wireSearch('.fv-filters .ca-search', document.getElementById('fvSearch'), (query) => {
    state.q = query;
    apply();
  });

  const reset = document.getElementById('fvReset');
  if (reset) {
    reset.addEventListener('click', () => {
      state.q = '';
      searchBox.clear();
      multi.reset();
      apply();
    });
  }

  // ---------- flip motion: staggered, random axis, alternating back ----------
  const BACKS = ['#19BAD1', '#F76C53'];
  const AXES = [
    ['rotateY(180deg)', 'rotateY(180deg)'],
    ['rotateY(-180deg)', 'rotateY(-180deg)'],
    ['rotateX(180deg)', 'rotateX(180deg)'],
    ['rotateX(-180deg)', 'rotateX(-180deg)'],
  ];
  let backIdx = 0;
  function roll(c) {
    const a = AXES[Math.floor(Math.random() * AXES.length)];
    c.style.setProperty('--rot', a[0]);
    c.style.setProperty('--brot', a[1]);
    c.style.setProperty('--fd', `${Math.round(Math.random() * 130)}ms`);
    c.style.setProperty('--bcol', BACKS[backIdx++ % 2]);
  }
  // Rolled once up front and again as the pointer arrives — never on focus.
  // Clicking a card focuses it, and re-rolling then changed the axis halfway
  // through the flip, which read as a glitch rather than a flourish.
  cards.forEach((c) => {
    roll(c);
    c.addEventListener('mouseenter', () => roll(c));
  });

  // ---------- a link can open the directory already filtered ----------
  // /founders-ventures?program=founder-one — the slugs the API's own filters use.
  // A value that is not an option on this page is dropped, so a link to a
  // programme the base does not have yet shows everything rather than nothing.
  const linked = parseFilters(location.search, DIMS.map((d) => d.key));
  DIMS.forEach((d) => multi.set(d.key, linked.values[d.key]));

  // ---------- deep link: /founders-ventures#ventures opens that tab ----------
  // Opened directly, not switched to — so it is already there when the page
  // paints rather than sliding in from the other tab.
  const want = (location.hash || '').replace('#', '');
  const wanted =
    want === 'founders' || want === 'ventures'
      ? document.querySelector(`.fv-tab[data-tab="${want}"]`)
      : null;
  if (wanted) activate(wanted, false);

  apply();
}
