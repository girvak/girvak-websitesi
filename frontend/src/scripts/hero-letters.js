// ============================================================
// GİRVAK showcase pages — hero headline, per-letter hover invert.
//
// Runs on import. Splits the `.fa-hero-title` into one span per letter so each
// can change colour under the pointer; the italic clause inverts the other way.
// Shared by the fellows, alumni and challengers pages.
// ============================================================

const title = document.querySelector('.fa-hero-title');
if (title) {
  [...title.childNodes].forEach((node) => {
    if (node.nodeType === 1 && node.tagName === 'I') {
      const frag = document.createDocumentFragment();
      for (const ch of node.textContent) {
        if (ch === ' ') { frag.appendChild(document.createTextNode(' ')); continue; }
        const s = document.createElement('span');
        s.className = 'ch-inv';
        s.textContent = ch;
        frag.appendChild(s);
      }
      node.textContent = '';
      node.appendChild(frag);
      return;
    }
    if (node.nodeType !== 3) return;
    const frag = document.createDocumentFragment();
    for (const ch of node.textContent) {
      if (ch === ' ') { frag.appendChild(document.createTextNode(' ')); continue; }
      const s = document.createElement('span');
      s.className = 'ch';
      s.textContent = ch;
      frag.appendChild(s);
    }
    title.replaceChild(frag, node);
  });
}
