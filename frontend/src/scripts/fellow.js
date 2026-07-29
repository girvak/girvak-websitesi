// ============================================================
// GİRVAK Fellow Program — hero crossfade (NATIVE scroll)
//
//  Scrolling is fully native — identical feel to the index / about
//  pages. NO wheel hijacking, NO snapping, NO scroll tweening.
//
//  The hero is a 200vh track whose inner panel is position:sticky, so it
//  pins for one viewport while you scroll past it. As the scroll crosses
//  the half-way point of the track, the left text binary-crossfades from
//  state A (motto) to state B (program description) via CSS .on/.off.
//  Past the track it releases into normal page flow.
// ============================================================
(function () {
  'use strict';

  var track = document.querySelector('.fhero-track');
  var s1 = document.querySelector('.fhero-1');
  var s2 = document.querySelector('.fhero-2');

  var mobile = window.matchMedia('(max-width: 1024px)');

  if (track && s1 && s2) {
    function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }

    // p = 0 → A fully visible ;  p = 1 → B fully visible
    function progress() {
      var total = track.offsetHeight - window.innerHeight;
      if (total <= 0) return 0;
      var base = window.scrollY + track.getBoundingClientRect().top;
      return clamp((window.scrollY - base) / total, 0, 1);
    }

    var active = -1;
    function setState(n) {
      if (mobile.matches) {
        s1.classList.remove('on', 'off');
        s2.classList.remove('on', 'off');
        active = -1;
        return;
      }
      if (n === active) return;
      active = n;
      s1.classList.toggle('on', n === 0);
      s1.classList.toggle('off', n !== 0);
      s2.classList.toggle('on', n === 1);
      s2.classList.toggle('off', n !== 1);
    }
    function sync() {
      if (mobile.matches) { setState(0); return; }
      setState(progress() >= 0.5 ? 1 : 0);
    }

    var ticking = false;
    window.addEventListener('scroll', function () {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(function () { sync(); ticking = false; });
      }
    }, { passive: true });
    window.addEventListener('resize', sync);
    mobile.addEventListener('change', sync);
    sync();
  }

  // Fellow / alumni / challenger belts — speed tuned in home.js (initAllFellowsBelts)

  // ---------- per-letter headline (hover colour swap) ----------
  var h1 = document.querySelector('.fhero-h1');
  if (h1) {
    function splitInto(parent, text, cls) {
      for (var i = 0; i < text.length; i++) {
        var c = text[i];
        if (c === ' ' || c === ' ') { parent.appendChild(document.createTextNode(c)); continue; }
        var sp = document.createElement('span');
        sp.className = cls;
        sp.textContent = c;
        parent.appendChild(sp);
      }
    }
    Array.prototype.slice.call(h1.childNodes).forEach(function (node) {
      if (node.nodeType === 3) {
        var frag = document.createDocumentFragment();
        splitInto(frag, node.textContent, 'ch');
        h1.replaceChild(frag, node);
      } else if (node.classList && node.classList.contains('hl')) {
        var t = node.textContent; node.textContent = '';
        splitInto(node, t, 'ch-inv');
      }
    });
  }
})();
