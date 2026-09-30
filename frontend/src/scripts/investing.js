// ============================================================
// GİRVAK Investing — the heading's letter hover, and the links' hover colour.
//
// The three links at the foot of the page take teal and coral in turn as the
// pointer arrives, as the design's inline script does.
// ============================================================
import './pp-heading.js';

const COLOURS = ['#19BAD1', '#F76C53'];
let next = 0;

document.querySelectorAll('.iv-link').forEach((link) => {
  link.addEventListener('mouseenter', () => {
    link.style.setProperty('--iv-hover', COLOURS[next % COLOURS.length]);
    next += 1;
  });
});
