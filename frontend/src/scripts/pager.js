// ============================================================
// GİRVAK showcase pages — "load more" arithmetic, and the filter <-> URL round
// trip. Pure functions only: nothing here touches the DOM, so they run under
// `node --test` (see tests/pager.test.js).
// ============================================================

/** Cards (or rows) revealed at first, and added by each "load more". */
export const PAGE_SIZE = 24;

/**
 * How many of the matched items are on screen.
 *
 * @param {number} matched  Items that pass the current filter.
 * @param {number} shown    How many the visitor has asked to see.
 * @returns {number}
 */
export function visibleCount(matched, shown) {
  return Math.max(0, Math.min(matched, shown));
}

/**
 * Is there anything left to reveal?
 *
 * @param {number} matched
 * @param {number} shown
 * @returns {boolean}
 */
export function hasMore(matched, shown) {
  return matched > shown;
}

/**
 * The status line under the grid: "showing 24 of 405 alumni".
 * Empty when nothing matches — the empty state says that already.
 *
 * @param {number} matched
 * @param {number} shown
 * @param {string} noun
 * @returns {string}
 */
export function summary(matched, shown, noun) {
  if (matched <= 0) return '';
  return `showing ${visibleCount(matched, shown)} of ${matched} ${noun}`;
}

/**
 * Filters from a query string. Values repeat (`?year=25&year=24`) to widen a
 * dropdown, exactly as the API's own filters do.
 *
 * @param {string} search  `location.search`.
 * @param {string[]} keys  The dropdown keys this page has.
 * @returns {{ q: string, values: Record<string, string[]> }}
 */
export function parseFilters(search, keys) {
  const params = new URLSearchParams(search);
  const values = {};
  keys.forEach((key) => {
    values[key] = [...new Set(params.getAll(key).map((v) => v.trim()).filter(Boolean))];
  });
  return { q: (params.get('q') || '').trim(), values };
}

/**
 * A query string for the current filters, `''` when none is set.
 *
 * @param {string} q
 * @param {Record<string, string[]>} values
 * @param {string[]} keys  Fixes the parameter order, so the same view is the same URL.
 * @returns {string}
 */
export function buildSearch(q, values, keys) {
  const params = new URLSearchParams();
  keys.forEach((key) => (values[key] || []).forEach((v) => params.append(key, v)));
  if (q) params.set('q', q);
  const out = params.toString();
  return out ? `?${out}` : '';
}
