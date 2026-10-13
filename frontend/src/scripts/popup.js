// ============================================================
// GİRVAK — home page popup of open calls.
//
// Opens a moment after the page loads, unless this browser already closed the
// same set of calls (`data-signature`; a new call or a changed deadline shows
// it again). Closes on the × , the backdrop, Escape, or a card being followed.
// While open, Tab stays inside it and the page behind does not scroll; on
// close, focus goes back where it was.
// ============================================================

const SEEN_KEY = 'girvak:popup-seen';
const OPEN_DELAY_MS = 1200;

const popup = document.getElementById('callPopup');
if (popup) {
  const signature = popup.dataset.signature ?? '';
  const row = popup.querySelector('.cp-row');
  let lastFocus = null;

  const seen = () => {
    try { return localStorage.getItem(SEEN_KEY) === signature; } catch { return false; }
  };
  const remember = () => {
    try { localStorage.setItem(SEEN_KEY, signature); } catch { /* private mode: it shows again next time */ }
  };

  const focusables = () =>
    [...popup.querySelectorAll('a[href], button, [tabindex]:not([tabindex="-1"])')].filter((el) => !el.hidden);

  const onKey = (e) => {
    if (e.key === 'Escape') { close(); return; }
    if (e.key !== 'Tab') return;
    const items = focusables();
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };

  function open() {
    // The menu may be open by now; the popup waits for the next visit then.
    if (document.getElementById('navmenu')?.classList.contains('open')) return;
    lastFocus = document.activeElement;
    popup.hidden = false;
    document.body.classList.add('cp-open');
    // A row that scrolls sideways must be reachable by keyboard to scroll it.
    // Measured now: while hidden it has no width.
    if (row && row.scrollWidth > row.clientWidth + 1) row.setAttribute('tabindex', '0');
    document.addEventListener('keydown', onKey);
    popup.querySelector('.cp-panel')?.focus();
  }

  function close() {
    if (popup.hidden) return;
    popup.hidden = true;
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
