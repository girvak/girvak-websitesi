// ============================================================
// GİRVAK — Apply / Open calls page behaviour.
//
// The page arrives sorted and with every card's state (open, closing soon,
// closed) already set — that is decided per request on the server, so it never
// depends on the visitor's clock. This only does what needs a browser:
//   - "see more": 8 cards at a time. Without JavaScript every card shows and
//     the button stays hidden.
//   - hover fills: the pinned (always-open) card is red, set in CSS; the others
//     alternate blue and coral on each hover, as do "see more" and the
//     "no open match" heading.
// ============================================================

const BLUE = '#19BAD1';
const CORAL = '#F76C53';
const PAGE_SIZE = 8;

const grid = document.getElementById('apGrid');
if (grid) {
  const cards = [...grid.querySelectorAll('.ap-card')];

  // ---- progressive disclosure ----
  const moreBtn = document.getElementById('apMore');
  let shown = PAGE_SIZE;
  const render = () => {
    cards.forEach((card, i) => { card.hidden = i >= shown; });
    if (moreBtn) moreBtn.hidden = cards.length <= shown;
  };
  if (moreBtn) {
    moreBtn.addEventListener('click', () => {
      const firstNew = cards[shown];
      shown += PAGE_SIZE;
      render();
      // Keep a keyboard user's place instead of dropping focus with the button,
      // which hides once nothing is left. Closed cards are not links, so they
      // take focus only from here (tabindex -1), never from Tab.
      if (firstNew) {
        if (!firstNew.matches('a')) firstNew.setAttribute('tabindex', '-1');
        firstNew.focus();
      }
    });
  }
  render();

  // ---- hover fills ----
  cards.forEach((card) => {
    if (card.classList.contains('is-pinned') || card.classList.contains('is-closed')) return;
    let n = 0;
    const toggle = () => {
      card.style.setProperty('--fill', n % 2 === 0 ? BLUE : CORAL);
      n += 1;
    };
    card.addEventListener('mouseenter', toggle);
    card.addEventListener('focus', toggle);
  });
}

let altIdx = 0;
[document.getElementById('apNoMatch')?.closest('.ap-shead-top'), document.getElementById('apMore')]
  .filter(Boolean)
  .forEach((target) => {
    target.addEventListener('mouseenter', () => {
      target.style.setProperty('--fill', altIdx % 2 === 0 ? BLUE : CORAL);
      altIdx += 1;
    });
  });
