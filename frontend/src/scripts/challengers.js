// ============================================================
// GİRVAK All Challengers — name search, dropdown filters and "load more" over
// a list
//
// Ported from the design project's challengers-all.js. The design kept its
// people in a hard-coded array and built the rows and dropdowns here; this page
// is server-rendered from the Airtable `people` table, so both already exist in
// the HTML and the script only toggles `hidden`.
//
// The design shows everyone at once; with a few hundred rows that is a very long
// page, so 24 are revealed at a time. Filters and search run over the whole
// list, not the revealed part.
//
// Filtering follows the founders & ventures page: a dimension is measured
// against the other filters but not its own, so each dropdown offers only what
// would still return a row.
// ============================================================
import { fold, hits, pruneOptions, wire, wireSearch } from './filters-multi.js';
import { PAGE_SIZE, initLoadMore, paginate } from './load-more.js';
import { buildSearch, parseFilters, visibleCount } from './pager.js';
import './hero-letters.js';

const rowsEl = document.getElementById('caRows');

if (rowsEl) {
  const rows = [...rowsEl.querySelectorAll('.ca-row')];
  const empty = document.getElementById('caEmpty');
  const reset = document.getElementById('caReset');
  const search = document.getElementById('caSearch');
  const state = { name: '', university: [], department: [], year: [] };

  // Rows carry their name already; fold it once so "ayse" finds "Ayşe".
  rows.forEach((r) => { r.dataset.name = fold(r.dataset.name || ''); });

  // Each row carries exactly one value per dimension, so nothing is split.
  const DIMS = ['university', 'department', 'year'];

  /** Does a row pass every dimension except, optionally, one of them? */
  function passes(r, skip) {
    if (state.name && r.dataset.name.indexOf(state.name) === -1) return false;
    return DIMS.every((key) => key === skip || hits(r.dataset[key], state[key]));
  }

  /** Narrow each dropdown to the choices that would actually return a row. */
  function refreshOptions() {
    pruneOptions({
      items: rows,
      dims: DIMS,
      passes,
      valuesOf: (r, key) => (r.dataset[key] ? [r.dataset[key]] : []),
      scopeFor: (key) => document.querySelector(`#caFilters .fv-filter[data-key="${key}"]`),
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
    matched = paginate(rows, passes, shown, animateFrom);
    if (empty) empty.hidden = matched > 0;
    refreshOptions();
    if (reset) reset.classList.toggle('is-live', !!state.name || filters.live());
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
    button: document.getElementById('caMoreBtn'),
    status: document.getElementById('caStatus'),
    noun: document.getElementById('caMore')?.dataset.noun || 'challengers',
    onMore() {
      const from = visibleCount(matched, shown);
      shown += PAGE_SIZE;
      render(from);
    },
  });

  const filters = wire('#caFilters .fv-filter:not(.ca-search)', state, apply);

  // The name column is a text search rather than a dropdown.
  const searchBox = wireSearch('#caFilters .ca-search', search, (query, raw) => {
    state.name = query;
    rawQuery = raw;
    apply();
  });

  if (reset) {
    reset.addEventListener('click', () => {
      state.name = '';
      rawQuery = '';
      searchBox.clear();
      filters.reset();
      apply();
    });
  }

  // ---------- a shared link opens the view it was copied from ----------
  const initial = parseFilters(location.search, DIMS);
  DIMS.forEach((key) => filters.set(key, initial.values[key]));
  if (initial.q) {
    rawQuery = initial.q;
    state.name = searchBox.set(initial.q);
  }

  apply();
}
