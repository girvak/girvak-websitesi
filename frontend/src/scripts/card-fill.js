// ============================================================
// GİRVAK — open call cards: the hover fill alternates blue and coral, one
// colour per hover, as the design's apply.js does. The pinned (always-open)
// card keeps its red and a closed card does not change, so both are skipped.
// Shared by the /apply grid and the home page popup.
// ============================================================

export const BLUE = '#19BAD1';
export const CORAL = '#F76C53';

/** @param {Element} card */
export function alternateFill(card) {
  if (!(card instanceof HTMLElement)) return;
  if (card.classList.contains('is-pinned') || card.classList.contains('is-closed')) return;
  let n = 0;
  const toggle = () => {
    card.style.setProperty('--fill', n % 2 === 0 ? BLUE : CORAL);
    n += 1;
  };
  card.addEventListener('mouseenter', toggle);
  card.addEventListener('focus', toggle);
}
