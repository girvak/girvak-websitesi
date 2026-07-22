// Alt homepage v3 — nav, rotator, horizontal depth picker, gallery sync
const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------- Nav scroll ----------
const nav = document.getElementById('altNav');
function onScroll() {
  if (nav) nav.classList.toggle('scrolled', window.scrollY > 12);
}
onScroll();
window.addEventListener('scroll', onScroll, { passive: true });

// ---------- Mobile nav ----------
const toggle = document.getElementById('altNavToggle');
const mobile = document.getElementById('altNavMobile');
if (toggle && mobile) {
  toggle.addEventListener('click', () => {
    const open = mobile.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
    mobile.setAttribute('aria-hidden', String(!open));
    document.body.classList.toggle('alt-nav-open', open);
  });
  mobile.querySelectorAll('a').forEach((a) => {
    a.addEventListener('click', () => {
      mobile.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
      mobile.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('alt-nav-open');
    });
  });
}

// ---------- Char-hover + word rotator ----------
function splitChars(el, cls) {
  const txt = el.textContent;
  el.textContent = '';
  for (let i = 0; i < txt.length; i++) {
    const ch = txt[i];
    if (ch === ' ' || ch === '\u00a0') {
      el.appendChild(document.createTextNode(ch));
      continue;
    }
    const s = document.createElement('span');
    s.className = cls;
    s.textContent = ch;
    el.appendChild(s);
  }
}

const heroBase = document.getElementById('heroBase');
if (heroBase) splitChars(heroBase, 'ch');

const heroRotator = document.getElementById('heroRotator');
if (heroRotator) {
  let WORDS = ['people', 'talent', 'dreams', 'future', 'changemakers', 'possibilities'];
  try {
    const fromData = JSON.parse(heroRotator.dataset.words || '[]');
    if (Array.isArray(fromData) && fromData.length) WORDS = fromData;
  } catch (_) { /* keep default */ }

  heroRotator.classList.add('word-rotator-container');

  function makeWord(w) {
    const el = document.createElement('span');
    el.className = 'word';
    el.textContent = w;
    splitChars(el, 'ch');
    const dot = document.createElement('span');
    dot.className = 'word-dot ch';
    dot.textContent = '.';
    el.appendChild(dot);
    return el;
  }

  const els = WORDS.map((w) => {
    const el = makeWord(w);
    el.classList.add('is-below');
    heroRotator.appendChild(el);
    return el;
  });

  requestAnimationFrame(() => {
    let max = 0;
    els.forEach((el) => { max = Math.max(max, el.scrollWidth); });
    if (max) heroRotator.style.minWidth = Math.ceil(max) + 'px';
  });

  els[0].classList.remove('is-below');
  els[0].classList.add('is-in');

  if (!reduce) {
    let cur = 0;
    const DWELL = 1700;
    const ROLL = 300;
    let timer = null;

    function tick() {
      const outEl = els[cur];
      const nxt = (cur + 1) % els.length;
      const inEl = els[nxt];
      outEl.classList.remove('is-in');
      outEl.classList.add('is-out');
      inEl.classList.remove('is-below');
      inEl.classList.add('is-in');
      setTimeout(() => {
        outEl.classList.remove('is-out');
        outEl.classList.add('is-below');
      }, ROLL);
      cur = nxt;
    }
    function start() { if (!timer) timer = setInterval(tick, DWELL); }
    function stop() { clearInterval(timer); timer = null; }
    heroRotator.addEventListener('mouseenter', stop);
    heroRotator.addEventListener('mouseleave', start);
    start();
  }
}

// ---------- Horizontal depth picker ----------
const pickerTrack = document.getElementById('pickerTrack');
const pickerStage = document.getElementById('pickerStage');
const gallery = document.getElementById('programGallery');
const meta = document.getElementById('programMeta');

const programsRegion = document.getElementById('programs');
const pickerDots = document.getElementById('pickerDots');

if (pickerTrack && pickerStage) {
  const cards = pickerTrack.querySelectorAll('.alt-picker-card');
  const gallerySets = gallery ? gallery.querySelectorAll('.alt-gallery-set') : [];
  const metaSets = meta ? meta.querySelectorAll('.alt-meta-set') : [];
  const dots = pickerDots ? pickerDots.querySelectorAll('.alt-picker-dot') : [];
  const total = cards.length;
  let active = 1;
  let timer = null;
  let paused = false;
  let interactive = false; // pointer over / keyboard focus within the picker

  function rel(i) {
    let d = i - active;
    if (d > total / 2) d -= total;
    if (d < -total / 2) d += total;
    return d;
  }

  function setActive(idx, fromUser) {
    active = ((idx % total) + total) % total;
    cards.forEach((card, i) => {
      card.classList.remove('slot-prev', 'slot-active', 'slot-next', 'slot-off');
      const d = rel(i);
      if (d === 0) card.classList.add('slot-active');
      else if (d === -1) card.classList.add('slot-prev');
      else if (d === 1) card.classList.add('slot-next');
      else card.classList.add('slot-off');
    });
    const key = String(active);
    gallerySets.forEach((s) => s.classList.toggle('is-active', s.dataset.program === key));
    metaSets.forEach((s) => s.classList.toggle('is-active', s.dataset.program === key));
    dots.forEach((dot, i) => {
      const on = i === active;
      dot.classList.toggle('is-active', on);
      dot.setAttribute('aria-selected', String(on));
    });
    if (fromUser) {
      paused = true;
      clearInterval(timer);
      timer = null;
    }
  }

  function step() {
    if (paused) return;
    setActive(active + 1, false);
  }

  function startPicker() {
    if (reduce || paused) return;
    if (!timer) timer = setInterval(step, 4000);
  }

  setActive(active, false);
  startPicker();

  pickerStage.addEventListener('mouseenter', () => {
    paused = true;
    clearInterval(timer);
    timer = null;
  });

  pickerStage.addEventListener('mouseleave', () => {
    paused = false;
    startPicker();
  });

  cards.forEach((card) => {
    card.addEventListener('click', (e) => {
      const idx = Number(card.dataset.index);
      const d = rel(idx);
      if (d === -1 || d === 1) {
        e.preventDefault();
        setActive(idx, true);
      }
    });
    card.addEventListener('mouseenter', () => {
      const idx = Number(card.dataset.index);
      if (rel(idx) === 0) return;
      paused = true;
      clearInterval(timer);
      timer = null;
      setActive(idx, false);
    });
  });

  dots.forEach((dot) => {
    dot.addEventListener('click', () => setActive(Number(dot.dataset.dot), true));
  });

  // Track whether the picker is the user's active focus, so we only capture
  // arrow keys there instead of hijacking them for the whole page.
  if (programsRegion) {
    programsRegion.addEventListener('mouseenter', () => { interactive = true; });
    programsRegion.addEventListener('mouseleave', () => { interactive = false; });
    programsRegion.addEventListener('focusin', () => { interactive = true; });
    programsRegion.addEventListener('focusout', (e) => {
      if (!programsRegion.contains(e.relatedTarget)) interactive = false;
    });
  }

  document.addEventListener('keydown', (e) => {
    if (!interactive) return;
    if (e.key === 'ArrowLeft') { e.preventDefault(); setActive(active - 1, true); }
    if (e.key === 'ArrowRight') { e.preventDefault(); setActive(active + 1, true); }
  });
}
