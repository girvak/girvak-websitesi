// ============================================================
// Shared multi-select filter mechanic (GİRVAK showcase pages).
//
// Ported from the design project's filters-multi.js. One change: it was a
// `window.GVF` global because the design pages load plain <script> tags; here
// Astro bundles ES modules, so it is an export and the global is gone.
//
//   wire(scopeSelector, state, apply, fills) -> { reset, live }
//
// State values for wired keys are ARRAYS — several values in one dropdown
// widen the filter (OR). Use hits() in apply().
// ============================================================

/**
 * Does one card's value satisfy a selection?
 *
 * @param {string} cardVal   The card's own value for this dimension.
 * @param {string[]} sel     Selected values; empty means "no filter".
 * @param {string} [split]   Separator, when the card carries several values.
 * @returns {boolean}
 */
export function hits(cardVal, sel, split) {
  if (!sel || !sel.length) return true;
  const vals = split
    ? String(cardVal || '').split(split).map((s) => s.trim())
    : [cardVal];
  return sel.some((v) => vals.indexOf(v) !== -1);
}

/**
 * Wire every filter dropdown inside a scope.
 *
 * @param {string} scopeSel  Selector matching each `.fv-filter` to wire.
 * @param {object} state     Mutated in place: one array per `data-key`.
 * @param {() => void} apply Re-runs the filter over the grid.
 * @param {string[]} [fills] Accent colours cycled as the visitor interacts.
 */
export function wire(scopeSel, state, apply, fills) {
  const palette = fills && fills.length ? fills : ['#19BAD1', '#F76C53'];
  let filterIdx = 0;
  let optIdx = 0;
  const recs = [];

  function closeAll() {
    document.querySelectorAll('.fv-filter.is-open').forEach((o) => {
      o.classList.remove('is-open');
      const b = o.querySelector('.fv-fbtn');
      if (b) b.setAttribute('aria-expanded', 'false');
    });
  }

  document.querySelectorAll(scopeSel).forEach((f) => {
    const btn = f.querySelector('.fv-fbtn');
    const key = f.dataset.key;
    if (!btn || !key) return;

    // The label element is rendered by the page, so unlike the design's version
    // there is no first-text-node surgery to do here.
    const lab = btn.querySelector('.fv-fbtn-label');
    if (!lab) return;
    const label = lab.textContent;

    const menu = f.querySelector('.fv-menu');
    if (menu) menu.setAttribute('aria-multiselectable', 'true');
    if (!Array.isArray(state[key])) state[key] = [];

    function paint() {
      const sel = state[key];
      f.classList.toggle('has-val', sel.length > 0);
      if (sel.length) {
        filterIdx += 1;
        f.style.setProperty('--fv-filter-fill', palette[filterIdx % palette.length]);
      } else {
        f.style.removeProperty('--fv-filter-fill');
      }
      // One selection reads as itself; several collapse to "first +n".
      const shown = f.querySelectorAll(`.fv-opt[data-val]:not([data-val=""])`);
      const labelFor = (v) => {
        const opt = [...shown].find((o) => o.dataset.val === v);
        return opt ? (opt.querySelector('.fv-opt-label') || opt).textContent.trim() : v;
      };
      lab.textContent =
        sel.length === 0
          ? label
          : sel.length === 1
            ? labelFor(sel[0])
            : `${labelFor(sel[0])} +${sel.length - 1}`;
      lab.title = sel.map(labelFor).join(', ');
    }

    recs.push({ el: f, key, lab, label, paint });

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = f.classList.contains('is-open');
      closeAll();
      if (!open) {
        f.classList.add('is-open');
        btn.setAttribute('aria-expanded', 'true');
      }
    });
    if (menu) {
      menu.addEventListener('click', (e) => {
        if (!e.target.closest('.fv-opt')) e.stopPropagation();
      });
    }

    f.querySelectorAll('.fv-opt').forEach((opt) => {
      opt.addEventListener('mouseenter', () => {
        optIdx += 1;
        opt.style.setProperty('--fv-opt-fill', palette[optIdx % palette.length]);
      });
      opt.addEventListener('click', (e) => {
        e.stopPropagation();
        const v = opt.dataset.val;
        if (!v) {
          // The "all …" row clears the dimension and closes the menu.
          state[key] = [];
          f.querySelectorAll('.fv-opt').forEach((o, i) => o.classList.toggle('is-on', i === 0));
          f.classList.remove('is-open');
          btn.setAttribute('aria-expanded', 'false');
        } else {
          const sel = state[key];
          const at = sel.indexOf(v);
          if (at === -1) sel.push(v);
          else sel.splice(at, 1);
          opt.classList.toggle('is-on', at === -1);
          opt.setAttribute('aria-selected', at === -1 ? 'true' : 'false');
          const allOpt = f.querySelector('.fv-opt[data-val=""]');
          if (allOpt) allOpt.classList.toggle('is-on', sel.length === 0);
        }
        paint();
        apply();
      });
    });
  });

  document.addEventListener('click', closeAll);

  return {
    reset() {
      recs.forEach((r) => {
        state[r.key] = [];
        r.el.querySelectorAll('.fv-opt').forEach((o, i) => o.classList.toggle('is-on', i === 0));
        r.paint();
      });
    },
    live() {
      return recs.some((r) => state[r.key].length > 0);
    },
    /**
     * Restore one dropdown's selection, e.g. from the URL. Values that are not
     * an option are dropped. Does not call `apply` — the caller repaints once.
     */
    set(key, values) {
      const r = recs.find((rec) => rec.key === key);
      if (!r) return;
      const known = [...r.el.querySelectorAll('.fv-opt[data-val]:not([data-val=""])')].map((o) => o.dataset.val);
      state[key] = values.filter((v) => known.indexOf(v) !== -1);
      r.el.querySelectorAll('.fv-opt').forEach((o) => {
        const v = o.dataset.val;
        const on = v ? state[key].indexOf(v) !== -1 : state[key].length === 0;
        o.classList.toggle('is-on', on);
        if (v) o.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      r.paint();
    },
  };
}

// ============================================================
// Shared by every showcase page (founders & ventures, fellows, alumni,
// challengers). These were copied into each page's script and had started to
// drift — one page's search did not fold Turkish letters — so they live here.
// ============================================================

const ASCII = { 'ı': 'i', 'ş': 's', 'ğ': 'g', 'ü': 'u', 'ö': 'o', 'ç': 'c' };

/**
 * Case- and diacritic-insensitive form of a string, so "ayse" finds "Ayşe".
 * Case the Turkish way (İ/I), then the Turkish letters down to ASCII.
 *
 * @param {string} value
 * @returns {string}
 */
export function fold(value) {
  return String(value).toLocaleLowerCase('tr').replace(/[ışğüöç]/g, (ch) => ASCII[ch]);
}

/**
 * Wire the search box that sits at the right of a filter bar.
 *
 * @param {string} wrapSel   Selector of the `.ca-search` wrapper.
 * @param {HTMLInputElement | null} input  Its text input.
 * @param {(query: string, raw: string) => void} onQuery  Called with the folded query and the text as typed.
 * @returns {{ clear: () => void, set: (raw: string) => string }}
 */
export function wireSearch(wrapSel, input, onQuery) {
  const wrap = document.querySelector(wrapSel);
  if (!wrap || !input) return { clear() {}, set: (raw) => fold(raw) };
  const btn = wrap.querySelector('.fv-fbtn');

  function close() {
    wrap.classList.remove('is-open');
    btn.setAttribute('aria-expanded', 'false');
  }

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = wrap.classList.contains('is-open');
    document.querySelectorAll('.fv-filter.is-open').forEach((o) => {
      o.classList.remove('is-open');
      const b = o.querySelector('.fv-fbtn');
      if (b) b.setAttribute('aria-expanded', 'false');
    });
    if (!open) {
      wrap.classList.add('is-open');
      btn.setAttribute('aria-expanded', 'true');
      input.focus();
    }
  });
  wrap.querySelector('.fv-menu').addEventListener('click', (e) => e.stopPropagation());
  input.addEventListener('input', () => {
    const raw = input.value.trim();
    const query = fold(raw);
    wrap.classList.toggle('has-val', !!query);
    onQuery(query, raw);
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === 'Escape') {
      close();
      input.blur();
    }
  });

  return {
    clear() {
      input.value = '';
      wrap.classList.remove('has-val');
      close();
    },
    /** Restore the text, e.g. from the URL; returns its folded form. Does not fire `onQuery`. */
    set(raw) {
      input.value = raw;
      wrap.classList.toggle('has-val', !!raw);
      return fold(raw);
    },
  };
}

/**
 * Narrow each dropdown to the choices that would actually return something.
 *
 * A dimension is measured against the *other* filters but not its own, so
 * picking one value prunes the other lists while leaving the rest of its own
 * list there to switch to. An option the visitor has already selected always
 * stays visible — hiding it would strand them with a filter they cannot lift.
 *
 * @param {object} o
 * @param {Element[]} o.items                Every card or row on the page.
 * @param {string[]} o.dims                  The dropdown keys.
 * @param {(item: Element, skip?: string) => boolean} o.passes  Item vs the filter, minus `skip`.
 * @param {(item: Element, key: string) => string[]} o.valuesOf  The values an item carries for a key.
 * @param {(key: string) => Element | null} o.scopeFor  The `.fv-filter` of a key.
 * @param {Record<string, string[]>} o.state  Current selections, one array per key.
 */
export function pruneOptions({ items, dims, passes, valuesOf, scopeFor, state }) {
  dims.forEach((key) => {
    const available = new Set();
    items.forEach((item) => {
      if (passes(item, key)) valuesOf(item, key).forEach((v) => available.add(v));
    });

    const scope = scopeFor(key);
    if (!scope) return;
    let live = 0;
    scope.querySelectorAll('.fv-opt').forEach((opt) => {
      const v = opt.dataset.val;
      if (!v) return; // the "all …" row is always offered
      const keep = available.has(v) || state[key].indexOf(v) !== -1;
      opt.hidden = !keep;
      if (keep) live += 1;
    });
    // Nothing left to choose: say so on the button rather than opening an
    // empty menu.
    scope.classList.toggle('is-exhausted', live === 0);
  });
}
