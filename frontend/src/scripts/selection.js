// ============================================================
// GİRVAK — text-selection colour that changes with every new selection.
//
// Each time the visitor starts a new selection (drag, double-click, Ctrl+A) the
// highlight takes the next colour in the page's palette, white text on top:
// blue, coral, grey — and on the Fellow and Challenger pages, yellow and
// red. The CSS reads `--sel-bg` / `--sel-fg` from the root; this script only
// moves them along. Extending a selection keeps its colour.
// ============================================================

/** Palettes as [background, text]. Yellow carries ink text: white would not read on it. */
export const PALETTES = {
  // The design's order (selection-cycle.js): blue, coral, grey.
  default: [
    ['var(--turquoise)', '#fff'],
    ['var(--coral)', '#fff'],
    ['var(--ink-700)', '#fff'],
  ],
  fellow: [
    ['var(--challenger)', 'var(--ink-800)'],
    ['var(--fellow)', '#fff'],
  ],
};

/** Body classes that switch to the yellow/red palette (fellows, challengers, fellow program). */
const FELLOW_CLASSES = ['fl', 'ca', 'fp'];

/**
 * Which palette a page uses.
 * @param {DOMTokenList | string[]} classes Body classes.
 * @returns {[string, string][]}
 */
export function paletteFor(classes) {
  const has = (c) => (typeof classes.contains === 'function' ? classes.contains(c) : classes.includes(c));
  return FELLOW_CLASSES.some(has) ? PALETTES.fellow : PALETTES.default;
}

/**
 * The next colour index, wrapping.
 * @param {number} index
 * @param {number} size
 * @returns {number}
 */
export function next(index, size) {
  return (index + 1) % size;
}

if (typeof document !== 'undefined') {
  const palette = paletteFor(document.body.classList);
  // One step before the first colour, so the first selection is the first colour.
  let index = palette.length - 1;
  let wasEmpty = true;
  const root = document.documentElement;
  const paint = () => {
    root.style.setProperty('--sel-bg', palette[index][0]);
    root.style.setProperty('--sel-fg', palette[index][1]);
  };
  paint();
  document.addEventListener('selectionchange', () => {
    const sel = document.getSelection();
    const empty = !sel || sel.isCollapsed;
    // A selection has just begun: move to the next colour for it.
    if (wasEmpty && !empty) {
      index = next(index, palette.length);
      paint();
    }
    wasEmpty = empty;
  });
}
