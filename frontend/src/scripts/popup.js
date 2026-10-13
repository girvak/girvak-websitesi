// ============================================================
// GİRVAK — home page popup of open calls.
//
// Opens a moment after the page loads, unless this browser already closed the
// same set of calls (`data-signature`; a new call or a changed deadline shows
// it again). Closes on the ×, the backdrop, Escape, or a call being followed.
// While open, Tab stays inside it and the page behind does not scroll; on
// close, focus goes back where it was.
//
// When there are more calls than fit (three on a wide screen, one on a phone)
// the row slides, one call per step: the arrows in the head, ← / → keys, a
// swipe or a sideways trackpad gesture, or the marks under the row. It also
// moves on by itself every few seconds, pausing while the pointer or focus is
// on the panel and stopping for good once the visitor slides it themselves.
// Not under reduced motion. The row moves by transform (`--at`), never by
// scrolling, so the calls in view are always whole; those out of view are
// `inert`, so Tab never lands on one.
// ============================================================

const SEEN_KEY = 'girvak:popup-seen';
const OPEN_DELAY_MS = 1200;
const AUTOPLAY_MS = 5000;
const SWIPE_PX = 40;

const popup = document.getElementById('callPopup');
if (popup) {
  const signature = popup.dataset.signature ?? '';
  const panel = popup.querySelector('.cp-panel');
  const row = popup.querySelector('.cp-row');
  const nav = popup.querySelector('.cp-nav');
  const prev = popup.querySelector('.cp-prev');
  const next = popup.querySelector('.cp-next');
  const dots = popup.querySelector('.cp-dots');
  const items = row ? [...row.children] : [];
  const track = popup.querySelector('.cp-track');
  const calm = window.matchMedia('(prefers-reduced-motion: reduce)');
  let lastFocus = null;
  let at = 0;

  const seen = () => {
    try { return localStorage.getItem(SEEN_KEY) === signature; } catch { return false; }
  };
  const remember = () => {
    try { localStorage.setItem(SEEN_KEY, signature); } catch { /* private mode: it shows again next time */ }
  };

  // ---- the slider ----
  /** Calls in view at once: `--v` on the panel (three at most; one on a phone). */
  const inView = () => (panel ? parseInt(getComputedStyle(panel).getPropertyValue('--v'), 10) || 1 : 1);
  /** Furthest step: how many calls are out of view to the right at the start. */
  const lastStep = () => Math.max(0, items.length - inView());

  function go(step) {
    at = Math.max(0, Math.min(lastStep(), step));
    render();
  }

  function render() {
    const end = lastStep();
    at = Math.min(at, end);
    row?.style.setProperty('--at', String(at));
    const shown = inView();
    items.forEach((item, i) => {
      const out = i < at || i >= at + shown;
      item.toggleAttribute('inert', out);
      if (out) item.setAttribute('aria-hidden', 'true');
      else item.removeAttribute('aria-hidden');
    });
    if (nav) nav.hidden = end === 0;
    if (prev) prev.disabled = at === 0;
    if (next) next.disabled = at >= end;
    if (!dots) return;
    if (dots.children.length !== (end === 0 ? 0 : end + 1)) {
      dots.replaceChildren();
      if (end > 0) {
        for (let i = 0; i <= end; i += 1) {
          const dot = document.createElement('button');
          dot.type = 'button';
          dot.className = 'cp-dot';
          // The arrows and ← / → are the keyboard's way; these are for the pointer.
          dot.tabIndex = -1;
          dot.addEventListener('click', () => { stopAutoplay(); go(i); });
          dots.appendChild(dot);
        }
      }
    }
    [...dots.children].forEach((dot, i) => dot.classList.toggle('is-on', i === at));
  }

  // ---- moving on by itself ----
  let timer = null;
  let paused = false;
  let stopped = false;

  function startAutoplay() {
    clearInterval(timer);
    timer = null;
    if (stopped || calm.matches || lastStep() === 0) return;
    timer = setInterval(() => {
      if (paused || popup.hidden) return;
      go(at >= lastStep() ? 0 : at + 1);
    }, AUTOPLAY_MS);
  }
  function stopAutoplay() {
    stopped = true;
    clearInterval(timer);
    timer = null;
  }

  // A swipe: one step per gesture, whichever way the finger went.
  let startX = null;
  track?.addEventListener('pointerdown', (e) => { if (e.pointerType !== 'mouse') startX = e.clientX; });
  track?.addEventListener('pointerup', (e) => {
    if (startX === null) return;
    const dx = e.clientX - startX;
    startX = null;
    if (Math.abs(dx) < SWIPE_PX) return;
    stopAutoplay();
    go(at + (dx < 0 ? 1 : -1));
  });
  track?.addEventListener('pointercancel', () => { startX = null; });
  // A sideways trackpad gesture: one step, then a pause so one flick is one step.
  let wheelLock = false;
  track?.addEventListener('wheel', (e) => {
    if (Math.abs(e.deltaX) <= Math.abs(e.deltaY) || Math.abs(e.deltaX) < 12 || lastStep() === 0) return;
    e.preventDefault();
    if (wheelLock) return;
    wheelLock = true;
    setTimeout(() => { wheelLock = false; }, 650);
    stopAutoplay();
    go(at + (e.deltaX > 0 ? 1 : -1));
  }, { passive: false });
  // The track clips the row; a browser bringing a focused call into view would
  // scroll it. Keep it still — the slider decides what is in view.
  track?.addEventListener('scroll', () => { track.scrollLeft = 0; });

  prev?.addEventListener('click', () => { stopAutoplay(); go(at - 1); });
  next?.addEventListener('click', () => { stopAutoplay(); go(at + 1); });
  panel?.addEventListener('pointerenter', () => { paused = true; });
  panel?.addEventListener('pointerleave', () => { paused = false; });
  panel?.addEventListener('focusin', (e) => { paused = e.target !== panel; });
  panel?.addEventListener('focusout', (e) => { if (!panel.contains(e.relatedTarget)) paused = false; });
  window.addEventListener('resize', () => { if (!popup.hidden) render(); });

  // ---- open / close ----
  const focusables = () =>
    [...popup.querySelectorAll('a[href], button:not([tabindex="-1"])')].filter((el) => !el.closest('[hidden], [inert]') && !el.disabled);

  const onKey = (e) => {
    if (e.key === 'Escape') { close(); return; }
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      if (lastStep() === 0) return;
      e.preventDefault();
      stopAutoplay();
      go(at + (e.key === 'ArrowRight' ? 1 : -1));
      return;
    }
    if (e.key !== 'Tab') return;
    const list = focusables();
    if (list.length === 0) return;
    const first = list[0];
    const last = list[list.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === panel)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };

  function open() {
    // The menu may be open by now; the popup waits for the next visit then.
    if (document.getElementById('navmenu')?.classList.contains('open')) return;
    lastFocus = document.activeElement;
    popup.hidden = false;
    document.body.classList.add('cp-open');
    document.addEventListener('keydown', onKey);
    panel?.focus();
    // Measured now: while hidden the panel's `--v` is not computed.
    render();
    startAutoplay();
  }

  function close() {
    if (popup.hidden) return;
    popup.hidden = true;
    clearInterval(timer);
    timer = null;
    document.body.classList.remove('cp-open');
    document.removeEventListener('keydown', onKey);
    remember();
    if (lastFocus instanceof HTMLElement) lastFocus.focus();
  }

  popup.querySelectorAll('[data-cp-close]').forEach((el) => el.addEventListener('click', close));
  // Following a call or "see all" counts as having seen it. A call opens in a
  // new tab, so the popup is closed for when the visitor comes back.
  popup.querySelectorAll('.cp-panel a[href]').forEach((a) => a.addEventListener('click', close));

  if (!seen()) setTimeout(open, OPEN_DELAY_MS);
}
