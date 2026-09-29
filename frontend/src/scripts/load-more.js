// ============================================================
// GİRVAK showcase pages — the "load more" button and the reveal itself.
//
// The whole list is in the HTML; what pages toggle is `hidden`. A card that is
// `hidden` never fetches its lazy photo, which is the point of showing 24 at a
// time: a 400-person list otherwise pulls tens of megabytes of portraits as the
// visitor scrolls.
//
// The next 24 load by themselves as the visitor nears the end of the list, so
// the page reads as one continuous scroll. The button stays as well: it is how a
// keyboard user asks for more, and what a browser without IntersectionObserver
// falls back to.
// ============================================================
import { PAGE_SIZE, hasMore, summary, visibleCount } from './pager.js';

/** How far below the viewport the end of the list may be before more loads. */
const LEAD = '300px';

/**
 * Show the first `shown` items that pass the filter, hide the rest.
 *
 * @param {HTMLElement[]} items  Every card or row, in page order.
 * @param {(item: HTMLElement) => boolean} passes  Item vs the current filter.
 * @param {number} shown  How many the visitor has asked to see.
 * @param {number} [animateFrom]  When >= 0, items revealed from this position
 *   on rise in one after another (a "load more", not a new filter).
 * @returns {number} How many items match the filter, shown or not.
 */
export function paginate(items, passes, shown, animateFrom = -1) {
  let matched = 0;
  items.forEach((el) => {
    el.classList.remove('lm-new');
    if (!passes(el)) {
      el.hidden = true;
      return;
    }
    const show = matched < shown;
    el.hidden = !show;
    if (show && animateFrom >= 0 && matched >= animateFrom) {
      el.style.setProperty('--i', Math.min(matched - animateFrom, 20));
      el.classList.add('lm-new');
    }
    matched += 1;
  });
  return matched;
}

/**
 * Wire the button and the status line under a list.
 *
 * @param {object} o
 * @param {HTMLButtonElement | null} o.button
 * @param {HTMLElement | null} o.status  `aria-live` line, "showing 24 of 405 alumni".
 * @param {string} o.noun  What the list holds, for the status line.
 * @param {() => void} o.onMore  Called on click, or when the end of the list comes
 *   into view; the page raises its `shown` and repaints.
 * @returns {{ update: (matched: number, shown: number) => void }}
 */
export function initLoadMore({ button, status, noun, onMore }) {
  if (button) button.addEventListener('click', onMore);

  // The block under the list is the trigger: when it is within LEAD of the
  // viewport, the visitor is at the end and the next 24 are due.
  const trigger = button ? button.closest('.lm') : null;
  const watcher =
    trigger && 'IntersectionObserver' in window
      ? new IntersectionObserver(
          (entries) => {
            if (entries.some((entry) => entry.isIntersecting) && !button.hidden) onMore();
          },
          { rootMargin: `0px 0px ${LEAD} 0px` },
        )
      : null;

  return {
    update(matched, shown) {
      if (status) status.textContent = summary(matched, shown, noun);
      if (!button) return;
      const more = hasMore(matched, shown);
      const hadFocus = document.activeElement === button;
      button.hidden = !more;
      if (watcher) {
        // An observer only reports a change. Watching again reports where the
        // trigger is now, so a short list or a tall screen keeps loading until
        // the end is out of reach — and stops when there is nothing left.
        watcher.unobserve(trigger);
        if (more) watcher.observe(trigger);
      }
      // The button the visitor just used is gone: leave focus on the line that
      // says how many they now see, rather than dropping it on the page.
      if (!more && hadFocus && status) status.focus();
    },
  };
}

export { PAGE_SIZE, visibleCount };
