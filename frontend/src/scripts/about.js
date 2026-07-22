// ============================================================
// GİRVAK — About page: hero headline per-letter hover split.
// Menu overlay + newsletter behaviour come from home.js (also imported).
// Splits the hero title into per-letter spans so each glyph inverts on hover
// (ink → teal), and the accent word inverts the other way (teal → ink),
// preserving the <br> line breaks.
// ============================================================
(function () {
  var heroTitle = document.querySelector('.ab-hero--home .ab-hero-title');
  if (!heroTitle) return;

  function isSpace(ch) { return ch === ' ' || ch.charCodeAt(0) === 160; }

  Array.prototype.slice.call(heroTitle.childNodes).forEach(function (node) {
    // accent word: split into per-letter spans that invert (teal → ink) on hover
    if (node.nodeType === 1 && node.classList && node.classList.contains('ab-accent')) {
      var atxt = node.textContent, afrag = document.createDocumentFragment();
      for (var j = 0; j < atxt.length; j++) {
        var ac = atxt[j];
        if (isSpace(ac)) { afrag.appendChild(document.createTextNode(ac)); continue; }
        var as = document.createElement('span'); as.className = 'ch-inv'; as.textContent = ac;
        afrag.appendChild(as);
      }
      node.textContent = '';
      node.appendChild(afrag);
      return;
    }
    if (node.nodeType !== 3) return; // skip <br> and the accent dot span
    var txt = node.textContent, frag = document.createDocumentFragment();
    for (var i = 0; i < txt.length; i++) {
      var c = txt[i];
      if (isSpace(c)) { frag.appendChild(document.createTextNode(c)); continue; }
      var s = document.createElement('span'); s.className = 'ch'; s.textContent = c;
      frag.appendChild(s);
    }
    heroTitle.replaceChild(frag, node);
  });
})();
