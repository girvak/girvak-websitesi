// ============================================================
// GİRVAK Programs & Projects family — the heading's per-letter hover.
//
// Ported from the design project's programs.js (its `splitLetters`). Runs on
// import. Every letter of `.pp-h1` becomes a span that turns teal under the
// pointer; the letters of the accent phrase keep the accent's class, so they
// turn the other way (teal to ink).
// ============================================================
const heading = document.querySelector('.pp-h1');

if (heading) {
  const frag = document.createDocumentFragment();
  [...heading.childNodes].forEach((node) => {
    const text = node.textContent ?? '';
    // A letter inside an element carries that element's class (`pp-accent`).
    const extra = node.nodeType === 1 ? ` ${node.className}` : '';
    for (const ch of text) {
      if (ch === ' ') {
        frag.appendChild(document.createTextNode(' '));
        continue;
      }
      const span = document.createElement('span');
      span.className = `ch${extra}`;
      span.textContent = ch;
      frag.appendChild(span);
    }
  });
  heading.textContent = '';
  heading.appendChild(frag);
}
