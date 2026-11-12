// ============================================================
// GİRVAK person cards — the flip follows the way the pointer came in.
//
// Enter from the left and the card turns away from the left edge; from the top,
// away from the top, and so on. Used by every flip card (directories, founders
// and ventures, the home belts), so there is one rule, not one per page.
// `entrySide` and `flipFor` are pure and tested (tests/card-direction.test.js).
// ============================================================

/**
 * Which edge of a box a point is closest to, measured in the box's own
 * proportions so a wide card is not biased toward its long sides.
 *
 * @param {{ left: number, top: number, width: number, height: number }} rect
 * @param {number} x Pointer x, viewport coordinates.
 * @param {number} y Pointer y, viewport coordinates.
 * @returns {'left' | 'right' | 'top' | 'bottom'}
 */
export function entrySide(rect, x, y) {
  const nx = (x - rect.left) / (rect.width || 1); // 0 left … 1 right
  const ny = (y - rect.top) / (rect.height || 1); // 0 top … 1 bottom
  const dist = { left: nx, right: 1 - nx, top: ny, bottom: 1 - ny };
  return /** @type {'left' | 'right' | 'top' | 'bottom'} */ (
    Object.keys(dist).reduce((a, b) => (dist[b] < dist[a] ? b : a))
  );
}

/**
 * The turn that sends the entered edge away from the viewer.
 * `axes: 'y'` limits it to a left/right turn, for cards whose back face is
 * fixed to a Y turn; a top or bottom entry then turns by the horizontal half.
 *
 * @param {'left' | 'right' | 'top' | 'bottom'} side
 * @param {'xy' | 'y'} [axes]
 * @param {boolean} [rightHalf] For `axes: 'y'` and a top/bottom entry: is the pointer right of centre?
 * @returns {string} A CSS transform.
 */
export function flipFor(side, axes = 'xy', rightHalf = false) {
  if (side === 'left') return 'rotateY(-180deg)';
  if (side === 'right') return 'rotateY(180deg)';
  if (axes === 'y') return rightHalf ? 'rotateY(180deg)' : 'rotateY(-180deg)';
  return side === 'top' ? 'rotateX(180deg)' : 'rotateX(-180deg)';
}

/**
 * Wire cards so each flips from the side the pointer entered. Sets `--rot` and
 * `--brot` (front/back turn, see ventures.css) and `--flip` (home belts).
 * Mouse only: touch and keyboard keep the CSS default.
 *
 * @param {Iterable<HTMLElement>} cards
 * @param {{ axes?: 'xy' | 'y' }} [options]
 */
export function wireFlipDirection(cards, { axes = 'xy' } = {}) {
  for (const card of cards) {
    card.addEventListener('pointerenter', (e) => {
      if (e.pointerType && e.pointerType !== 'mouse') return;
      const rect = card.getBoundingClientRect();
      const side = entrySide(rect, e.clientX, e.clientY);
      const turn = flipFor(side, axes, e.clientX > rect.left + rect.width / 2);
      card.style.setProperty('--rot', turn);
      card.style.setProperty('--brot', turn);
      card.style.setProperty('--flip', turn);
      card.style.setProperty('--fd', '0ms');
    });
  }
}
