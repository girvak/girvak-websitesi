// ============================================================
// GİRVAK — the numbers on a program page count up when they scroll into view.
//
// Each `[data-count]` holds its final value in the HTML (so it reads right with
// no script); this resets it to 0 and counts up once it is on screen. `data-pre`
// and `data-suf` are the text before and after, `data-decimals` the places and
// `data-group` ("1") asks for thousands separators.
// Reduced motion keeps the final numbers. `formatCount` and `easeOut` are pure
// and tested (tests/count-up.test.js).
// ============================================================

/**
 * The text of a counter.
 * @param {number} value
 * @param {number} decimals
 * @param {string} [prefix]
 * @param {string} [suffix]
 * @param {boolean} [grouped] Print thousands separators ("1,076"), as the editor wrote the figure.
 * @returns {string}
 */
export function formatCount(value, decimals, prefix = '', suffix = '', grouped = false) {
  const digits = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    useGrouping: grouped,
  }).format(value);
  return `${prefix}${digits}${suffix}`;
}

/**
 * Ease-out cubic, 0 → 1.
 * @param {number} t Progress from 0 to 1.
 * @returns {number}
 */
export function easeOut(t) {
  const x = Math.min(1, Math.max(0, t));
  return 1 - (1 - x) ** 3;
}

const DURATION_MS = 1400;

/** @param {HTMLElement} el */
function run(el) {
  const to = Number(el.dataset.count);
  const decimals = Number(el.dataset.decimals || 0);
  const { pre = '', suf = '' } = el.dataset;
  const grouped = el.dataset.group === '1';
  if (!Number.isFinite(to)) return;
  el.textContent = formatCount(0, decimals, pre, suf, grouped);
  let start = 0;
  /** @param {number} now */
  const frame = (now) => {
    if (!start) start = now;
    const t = (now - start) / DURATION_MS;
    el.textContent = formatCount(to * easeOut(t), decimals, pre, suf, grouped);
    if (t < 1) requestAnimationFrame(frame);
    else el.textContent = formatCount(to, decimals, pre, suf, grouped);
  };
  requestAnimationFrame(frame);
}

/** Wire every `[data-count]` on the page. */
export function initCountUp() {
  const els = [...document.querySelectorAll('[data-count]')];
  if (els.length === 0) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
  const seen = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      seen.unobserve(entry.target);
      run(/** @type {HTMLElement} */ (entry.target));
    }
  }, { threshold: 0.4 });
  els.forEach((el) => seen.observe(el));
}

if (typeof document !== 'undefined') initCountUp();
