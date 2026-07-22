// ============================================================
// GİRVAK homepage — interactions (vanilla, bundled by Astro)
// ============================================================
const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------- NAV scroll state ----------
const nav = document.querySelector('.hm-nav');
// `.ab-nav` pages (white hero from the top) stay permanently scrolled — don't toggle.
function onScroll() { if (nav && !nav.classList.contains('ab-nav')) nav.classList.toggle('scrolled', window.scrollY > 40); }
onScroll();
window.addEventListener('scroll', onScroll, { passive: true });

// ---------- What-we-do flip cards: tap to flip on touch ----------
const canHover = window.matchMedia('(hover: hover)').matches;
if (!canHover) {
  document.querySelectorAll('.wd-card').forEach((card) => {
    card.addEventListener('click', (e) => {
      if (!card.classList.contains('is-flipped')) {
        e.preventDefault();
        document.querySelectorAll('.wd-card.is-flipped').forEach((o) => { if (o !== card) o.classList.remove('is-flipped'); });
        card.classList.add('is-flipped');
      }
    });
  });
}

// ---------- Full-page menu overlay ----------
const navmenu = document.getElementById('navmenu');
const menuOpen = document.getElementById('menuOpen');
const menuClose = document.getElementById('menuClose');
function openMenu() {
  if (!navmenu) return;
  navmenu.classList.add('open');
  navmenu.setAttribute('aria-hidden', 'false');
  if (menuOpen) menuOpen.setAttribute('aria-expanded', 'true');
  document.body.classList.add('menu-open');
}
function closeMenu() {
  if (!navmenu) return;
  navmenu.classList.remove('open');
  navmenu.setAttribute('aria-hidden', 'true');
  if (menuOpen) menuOpen.setAttribute('aria-expanded', 'false');
  document.body.classList.remove('menu-open');
}
if (menuOpen) menuOpen.addEventListener('click', () => { navmenu && navmenu.classList.contains('open') ? closeMenu() : openMenu(); });
if (menuClose) menuClose.addEventListener('click', closeMenu);
if (navmenu) navmenu.querySelectorAll('.nm-head, .nm-sub a, .navmenu-apply').forEach((a) => {
  a.addEventListener('click', (e) => {
    // Let in-page anchors navigate; placeholder "#" links just close the menu.
    closeMenu();
  });
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && navmenu && navmenu.classList.contains('open')) closeMenu();
});
if (navmenu) {
  navmenu.querySelectorAll('.nm-item').forEach((item) => {
    if (!item.querySelector('.nm-sub')) return;
    item.addEventListener('mouseenter', () => {
      navmenu.querySelectorAll('.nm-item.is-open').forEach((o) => { if (o !== item) o.classList.remove('is-open'); });
      item.classList.add('is-open');
    });
    item.addEventListener('mouseleave', () => { item.classList.remove('is-open'); });
  });
  navmenu.addEventListener('click', (e) => {
    if (!e.target.closest('a, button')) closeMenu();
  });
}

// ---------- Reveal on scroll ----------
let revealEls = [].slice.call(document.querySelectorAll('.rv'));
function checkReveal() {
  const vh = window.innerHeight || document.documentElement.clientHeight;
  revealEls = revealEls.filter((el) => {
    const r = el.getBoundingClientRect();
    if (r.top < vh * 0.9 && r.bottom > 0) { el.classList.add('in'); return false; }
    return true;
  });
}
window.addEventListener('scroll', () => { requestAnimationFrame(checkReveal); }, { passive: true });
window.addEventListener('resize', checkReveal);
checkReveal();
setTimeout(() => { revealEls.forEach((el) => el.classList.add('in')); }, 2200);

// ---------- HERO image belt (seamless marquee) ----------
const belt3 = document.getElementById('belt3');
if (belt3) {
  const track = belt3.querySelector('.belt3-track');
  if (track) track.innerHTML += track.innerHTML;
}

// ---------- Fellows belt (seamless marquee + random Airtable spotlight) ----------
// Same linear speed everywhere: homepage reference ≈ 8 cards in 110s per half-loop.
const FELLOWS_BELT_HALF_LOOP_SEC = 110;
const FELLOWS_BELT_REF_CARD_COUNT = 8;
const FELLOWS_BELT_REF_CARD_STEP_PX = 258; // ~232px card + gap at desktop
const FELLOWS_BELT_PX_PER_SEC =
  (FELLOWS_BELT_REF_CARD_COUNT * FELLOWS_BELT_REF_CARD_STEP_PX) / FELLOWS_BELT_HALF_LOOP_SEC;

function finalizeFellowsTrack(track) {
  if (!track || reduce) return;
  if (track.dataset.beltDuplicated !== '1') {
    track.innerHTML += track.innerHTML;
    track.dataset.beltDuplicated = '1';
  }
  const half = track.scrollWidth / 2;
  if (half > 0) {
    const sec = half / FELLOWS_BELT_PX_PER_SEC;
    track.style.setProperty('--fellows-belt-duration', `${sec}s`);
  }
}

function initAllFellowsBelts() {
  document.querySelectorAll('.fellows-track').forEach((track) => {
    if (track.dataset.spotlightFetch === 'true') return;
    finalizeFellowsTrack(track);
  });
}

const COLOR_CLASS = { teal: 'fc-teal', coral: 'fc-coral', ink: 'fc-ink' };

function escHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/"/g, '&quot;');
}

function fellowCardMarkup(f) {
  const cls = COLOR_CLASS[f.color] || 'fc-teal';
  const yearFront = f.year ? `<span class="fcard-year">${escHtml(f.year)}</span>` : '';
  const yearBack = f.year ? `<span class="fcard-back-year">${escHtml(f.year)}</span>` : '';
  const img = f.image
    ? `<img src="${escHtml(f.image)}" alt="${escHtml(f.name)}" loading="lazy" decoding="async" />`
    : '';
  const uni = f.university ? `<span class="fcard-uni">${escHtml(f.university)}</span>` : '';
  const dept = f.department ? `<span class="fcard-dept">${escHtml(f.department)}</span>` : '';
  return (
    `<figure class="fcard ${cls}" tabindex="0">` +
      '<div class="fcard-inner">' +
        '<div class="fcard-front">' +
          yearFront +
          img +
          `<div class="fcard-band"><span class="fcard-frontname">${escHtml(f.name)}</span></div>` +
        '</div>' +
        '<div class="fcard-back">' +
          yearBack +
          '<div class="fcard-back-meta">' +
            `<span class="fcard-name">${escHtml(f.name)}</span>` +
            uni +
            dept +
          '</div>' +
        '</div>' +
      '</div>' +
    '</figure>'
  );
}

async function initFellowsBelt() {
  const track = document.getElementById('belt');
  if (!track || track.dataset.spotlightFetch !== 'true') return;
  try {
    const res = await fetch('/api/content/fellows-spotlight');
    if (res.ok) {
      const fellows = await res.json();
      if (Array.isArray(fellows) && fellows.length) {
        track.innerHTML = fellows.map(fellowCardMarkup).join('');
        track.dataset.beltDuplicated = '0';
      }
    }
  } catch (_) {
    /* keep SSR cards from build / first paint */
  }
  finalizeFellowsTrack(track);
}

initFellowsBelt();
initAllFellowsBelts();
window.addEventListener('load', initAllFellowsBelts, { passive: true });
window.addEventListener('resize', () => {
  requestAnimationFrame(initAllFellowsBelts);
}, { passive: true });

// ---------- Headline: char-hover + word rotator ----------
function splitChars(el, cls) {
  const txt = el.textContent;
  el.textContent = '';
  for (let i = 0; i < txt.length; i++) {
    const ch = txt[i];
    if (ch === ' ' || ch === ' ') { el.appendChild(document.createTextNode(ch)); continue; }
    const s = document.createElement('span');
    s.className = cls;
    s.textContent = ch;
    el.appendChild(s);
  }
}
const heroBase = document.getElementById('heroBase');
// Base line stays plain text so the headline wraps naturally (no per-letter spans).

const heroRotator = document.getElementById('heroRotator');
if (heroRotator) {
  let WORDS = ['people', 'talent', 'dreams', 'future', 'changemakers', 'possibilities'];
  try {
    const fromData = JSON.parse(heroRotator.dataset.words || '[]');
    if (Array.isArray(fromData) && fromData.length) WORDS = fromData;
  } catch (_) { /* keep default */ }

  if (!heroRotator.classList.contains('word-rotator-container')) {
    heroRotator.classList.add('word-rotator-container');
  }

  function makeWord(w) {
    const el = document.createElement('span');
    el.className = 'word';
    el.textContent = w;
    const dot = document.createElement('span');
    dot.className = 'word-dot';
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
    const measure = () => {
      let max = 0;
      els.forEach((el) => { max = Math.max(max, el.scrollWidth); });
      if (max) heroRotator.style.minWidth = `${Math.ceil(max + 2)}px`;
    };
    measure();
    if (document.fonts?.ready) document.fonts.ready.then(measure);
    window.addEventListener('resize', measure, { passive: true });
  });

  els[0].classList.remove('is-below');
  els[0].classList.add('is-in');

  if (!reduce) {
    let cur = 0;
    const DWELL = 1200;
    const ROLL = 290;
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

// ---------- Count-up numbers ----------
let counted = [].slice.call(document.querySelectorAll('[data-count]'));
function fmt(v, el) {
  const dec = +(el.dataset.dec || 0);
  const pre = el.dataset.pre || '';
  const suf = el.dataset.suf || '';
  const s = dec > 0 ? v.toFixed(dec) : Math.round(v).toLocaleString('en-US');
  return pre + s + suf;
}
function runCount(el) {
  const to = parseFloat(el.dataset.count);
  const dur = 1500;
  if (reduce) { el.textContent = fmt(to, el); return; }
  let startT = null;
  function tick(t) {
    if (!startT) startT = t;
    const p = Math.min((t - startT) / dur, 1);
    const e = 1 - Math.pow(1 - p, 3);
    el.textContent = fmt(to * e, el);
    if (p < 1) requestAnimationFrame(tick); else el.textContent = fmt(to, el);
  }
  requestAnimationFrame(tick);
  setTimeout(() => { el.textContent = fmt(to, el); }, dur + 400);
}
function checkCount() {
  const vh = window.innerHeight;
  counted = counted.filter((el) => {
    const r = el.getBoundingClientRect();
    if (r.top < vh * 0.85 && r.bottom > 0) { runCount(el); return false; }
    return true;
  });
}
window.addEventListener('scroll', () => { requestAnimationFrame(checkCount); }, { passive: true });
checkCount();
setTimeout(checkCount, 600);

// ---------- Newsletter (posts to FastAPI) ----------
const form = document.querySelector('.ft-form');
if (form) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = form.querySelector('input');
    const btn = form.querySelector('button');
    const lbl = btn && btn.querySelector('.ft-sub-label');
    const email = input ? input.value.trim() : '';
    if (!email) return;
    const apiBase = form.dataset.api || '';
    try {
      const res = await fetch(`${apiBase}/api/newsletter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      form.classList.add('ok');
      if (lbl) lbl.textContent = data.status === 'already_subscribed' ? 'Already in ✓' : 'Subscribed ✓';
      if (input) input.value = '';
    } catch (err) {
      if (lbl) lbl.textContent = 'Try again';
      console.error('[newsletter]', err);
    }
  });
}
