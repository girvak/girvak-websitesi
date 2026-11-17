// ============================================================
// GİRVAK — scroll an in-page heading to the top, just under the fixed nav.
//
// Used by tabs and panels (ventures.js, programs.js). The nav's height is
// measured on every call, not assumed: it changes with the viewport (padding
// and menu icon are clamp()ed), so a fixed offset left headings under it.
// Content above the target can still move while a smooth scroll runs (a panel
// fading in from -8px, a tab swapping its cards), so the position is checked
// once more when the scroll ends and corrected without animation.
// ============================================================

/** Space between the nav's bottom edge and the heading. */
export const GAP = 16;
/** A miss smaller than this is not worth a second jump. */
const TOLERANCE = 2;
/** Stop waiting for the scroll to end after this long (ms). */
const SETTLE_MS = 1200;

/**
 * Where to scroll so an element sits just under the nav. Pure.
 *
 * @param {number} elTop     Element's top, relative to the viewport.
 * @param {number} scrollY   Current scroll position.
 * @param {number} navBottom Nav's bottom edge, relative to the viewport.
 * @param {number} maxY      Largest scroll position the page allows.
 * @param {number} [gap]
 * @returns {number}
 */
export function targetY(elTop, scrollY, navBottom, maxY, gap = GAP) {
  const y = Math.round(elTop + scrollY - navBottom - gap);
  return Math.min(Math.max(0, y), Math.max(0, maxY));
}

function navBottom() {
  const nav = document.querySelector('.hm-nav');
  return nav ? Math.max(0, nav.getBoundingClientRect().bottom) : 0;
}

function goal(el) {
  const maxY = document.documentElement.scrollHeight - window.innerHeight;
  return targetY(el.getBoundingClientRect().top, window.scrollY, navBottom(), maxY);
}

/**
 * Bring `el` to the top of the page, under the nav.
 *
 * @param {Element | null} el
 */
export function scrollToTop(el) {
  if (!el) return;
  const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const y = goal(el);
  if (Math.abs(y - window.scrollY) <= TOLERANCE) return;
  window.scrollTo({ top: y, behavior: calm ? 'auto' : 'smooth' });
  if (calm) return;

  let done = false;
  const settle = () => {
    if (done) return;
    done = true;
    window.removeEventListener('scrollend', settle);
    const again = goal(el);
    if (Math.abs(again - window.scrollY) > TOLERANCE) window.scrollTo({ top: again, behavior: 'auto' });
  };
  if ('onscrollend' in window) window.addEventListener('scrollend', settle, { once: true });
  window.setTimeout(settle, SETTLE_MS);
}

/**
 * Arriving on /page#section: the browser jumps before fonts and images have
 * finished laying out, so the heading can end up a little off. Once the page
 * has loaded, put it back under the nav — unless the visitor has already
 * scrolled away on their own (more than a screen's worth of difference).
 */
export function realignHashOnLoad() {
  const id = decodeURIComponent(location.hash.slice(1));
  if (!id) return;
  const fix = () => {
    const el = document.getElementById(id);
    if (!el) return;
    const y = goal(el);
    const off = Math.abs(y - window.scrollY);
    if (off > TOLERANCE && off < window.innerHeight) window.scrollTo({ top: y, behavior: 'auto' });
  };
  if (document.readyState === 'complete') fix();
  else window.addEventListener('load', fix, { once: true });
}
