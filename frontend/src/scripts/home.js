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
  navmenu.querySelectorAll('.nm-item.is-open').forEach((o) => o.classList.remove('is-open'));
}
if (menuOpen) menuOpen.addEventListener('click', () => { navmenu && navmenu.classList.contains('open') ? closeMenu() : openMenu(); });
if (menuClose) menuClose.addEventListener('click', closeMenu);
if (navmenu) {
  navmenu.querySelectorAll('.nm-sub a, .navmenu-apply, .nm-item-apply > .nm-head').forEach((a) => {
    a.addEventListener('click', () => { closeMenu(); });
  });
}
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && navmenu && navmenu.classList.contains('open')) closeMenu();
});
if (navmenu) {
  navmenu.querySelectorAll('.nm-item').forEach((item) => {
    if (!item.querySelector('.nm-sub')) return;
    const head = item.querySelector('.nm-head');
    item.addEventListener('mouseenter', () => {
      if (!canHover) return;
      navmenu.querySelectorAll('.nm-item.is-open').forEach((o) => { if (o !== item) o.classList.remove('is-open'); });
      item.classList.add('is-open');
    });
    item.addEventListener('mouseleave', () => {
      if (!canHover) return;
      item.classList.remove('is-open');
    });
    if (head) {
      head.addEventListener('click', (e) => {
        if (canHover) {
          // Desktop: follow the head link and close the overlay.
          closeMenu();
          return;
        }
        // Touch: first tap opens accordion; second tap (already open) navigates.
        if (!item.classList.contains('is-open')) {
          e.preventDefault();
          navmenu.querySelectorAll('.nm-item.is-open').forEach((o) => {
            if (o !== item) o.classList.remove('is-open');
          });
          item.classList.add('is-open');
          return;
        }
        closeMenu();
      });
    }
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
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function linkedInHref(raw) {
  if (!raw) return undefined;
  const first = String(raw).trim().split(/\s+/)[0] || '';
  if (!first || first === '#') return undefined;
  // Ignore non-profile tokens like "linkedin.com"
  if (/linkedin\.com\/?$/i.test(first.replace(/\/$/, ''))) return undefined;
  const href = /^https?:\/\//i.test(first) ? first : `https://${first.replace(/^\/+/, '')}`;
  return /linkedin\.com\/in\//i.test(href) ? href : undefined;
}

function personName(p) {
  return [p.first, p.last].filter(Boolean).join(' ');
}

const PALETTE = ['fc-teal', 'fc-coral', 'fc-ink'];

function fellowCardMarkup(p, index) {
  const cls = PALETTE[index % PALETTE.length];
  const name = personName(p);
  const yearFront = p.year ? `<span class="fcard-year">${escHtml(p.year)}</span>` : '';
  const yearBack = p.year ? `<span class="fcard-back-year">${escHtml(p.year)}</span>` : '';
  const img = p.photo
    ? `<img src="${escHtml(p.photo)}" alt="${escHtml(name)}" loading="lazy" decoding="async" />`
    : '';
  const uni = (p.university || p.company)
    ? `<span class="fcard-uni">${escHtml(p.university || p.company)}</span>`
    : '';
  const dept = p.department ? `<span class="fcard-dept">${escHtml(p.department)}</span>` : '';
  const linkedin = linkedInHref(p.linkedin);
  const linkedinAttr = linkedin ? ` data-linkedin="${escHtml(linkedin)}"` : '';
  return (
    `<figure class="fcard ${cls}" tabindex="0"${linkedinAttr}>` +
      '<div class="fcard-inner">' +
        '<div class="fcard-front">' +
          yearFront +
          img +
          `<div class="fcard-band"><span class="fcard-frontname">${escHtml(name)}</span></div>` +
        '</div>' +
        '<div class="fcard-back">' +
          yearBack +
          '<div class="fcard-back-meta">' +
            `<span class="fcard-name">${escHtml(name)}</span>` +
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
  // Re-sampling the spotlight at runtime is a dev convenience. In production it
  // would swap the build's optimized <picture> markup for raw backend image
  // URLs and make the API a hard dependency of the homepage, so the cards baked
  // at build time stay put (they are already a fresh random sample per build).
  if (import.meta.env.DEV) {
    try {
      const res = await fetch('/api/content/fellows-spotlight');
      if (res.ok) {
        const fellows = await res.json();
        if (Array.isArray(fellows) && fellows.length) {
          track.innerHTML = fellows.map((f, i) => fellowCardMarkup(f, i)).join('');
          track.dataset.beltDuplicated = '0';
        }
      }
    } catch (_) {
      /* keep SSR cards from build / first paint */
    }
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
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await res.json();
      form.classList.add('ok');
      if (lbl) lbl.textContent = 'Subscribed ✓';
      if (input) input.value = '';
    } catch (err) {
      if (lbl) lbl.textContent = 'Try again';
      console.error('[newsletter]', err);
    }
  });
}

// ---------- Fellow / challenger cards → LinkedIn on click (desktop + mobile) ----------
// Use event delegation so dynamically injected cards also work.
document.addEventListener('click', (e) => {
  const fcard = e.target && e.target.closest ? e.target.closest('.fcard') : null;
  if (fcard) {
    const linkedIn = fcard.getAttribute('data-linkedin') || '';
    if (linkedIn) {
      e.preventDefault();
      window.open(linkedIn, '_blank', 'noopener,noreferrer');
    }
    return;
  }

  const cchcard = e.target && e.target.closest ? e.target.closest('.cchcard') : null;
  if (cchcard) {
    const linkedIn = cchcard.getAttribute('data-linkedin') || '';
    if (!linkedIn) return;
    e.preventDefault();
    window.open(linkedIn, '_blank', 'noopener,noreferrer');
  }
});

// ---------- Touch: fellow flip cards + people curtain cards ----------
if (!canHover) {
  // Touch flip: delegate so dynamically injected cards also work.
  document.addEventListener('click', (e) => {
    const card = e.target && e.target.closest ? e.target.closest('.fcard') : null;
    if (!card) return;
    if (card.getAttribute('data-linkedin')) return; // LinkedIn has priority

    e.preventDefault();
    const open = card.classList.contains('is-flipped');
    document.querySelectorAll('.fcard.is-flipped').forEach((o) => {
      if (o !== card) o.classList.remove('is-flipped');
    });
    card.classList.toggle('is-flipped', !open);
  });

  document.querySelectorAll('.bcard').forEach((card) => {
    card.addEventListener('click', (e) => {
      const isLink = card.tagName === 'A';
      const open = card.classList.contains('is-open');
      if (!open) {
        // First tap reveals details; second tap follows LinkedIn (if any).
        e.preventDefault();
        document.querySelectorAll('.bcard.is-open').forEach((o) => {
          if (o !== card) o.classList.remove('is-open');
        });
        card.classList.add('is-open');
        return;
      }
      if (!isLink) e.preventDefault();
    });
  });

  // Tap empty belt chrome to pause/resume marquees (cards handle their own taps).
  document.querySelectorAll('.fellows-belt, .hero3-belt-wrap').forEach((belt) => {
    belt.addEventListener('click', (e) => {
      if (e.target.closest('.fcard, .b3card, a, button')) return;
      belt.classList.toggle('is-paused');
    });
  });
}
