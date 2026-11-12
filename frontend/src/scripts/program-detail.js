// ============================================================
// GİRVAK program page (/programs/<slug>) — behaviour.
//
// The headline's letters change colour under the pointer (hero-letters.js), the
// numbers count up (count-up.js), and the links at the foot alternate blue and
// coral on each hover, as on the design.
// ============================================================
import './home.js';
import './hero-letters.js';
import './count-up.js';

const COLOURS = ['#19BAD1', '#F76C53'];
let turn = 0;
document.querySelectorAll('.pd-link').forEach((link) => {
  link.addEventListener('mouseenter', () => {
    link.style.setProperty('--pd-hover', COLOURS[turn++ % 2]);
  });
});
