# Showcase pages

`/founders-ventures`, `/fellows`, `/alumni`, `/challengers` and
`/board-of-trustees` are the site's directories: a hero and a list of people or
ventures, and — on all but the board — a filter bar. They share one filter bar and
one set of behaviours, so a change to it is a change to all of them. This page says where each piece lives and which rules are deliberate.

## Where things are

| Piece | File |
|---|---|
| Fellows, alumni and trustees body (hero, filter bar, cards) | `src/components/PeopleDirectory.astro` |
| Challengers page (a list, not cards) | `src/pages/challengers.astro` |
| Founders & ventures page (two tabs) | `src/pages/founders-ventures.astro` |
| Shared filter bar behaviour | `src/scripts/filters-multi.js` — `wire`, `wireSearch`, `pruneOptions`, `fold`, `hits` |
| "Load more" reveal | `src/scripts/load-more.js` |
| Reveal arithmetic and the filter ↔ URL round trip (pure) | `src/scripts/pager.js` |
| Hero headline letter effect | `src/scripts/hero-letters.js` |
| Page scripts | `directory.js` (fellows, alumni), `challengers.js`, `ventures.js` |
| Styles | `ventures.css` (shell, filter bar, cards), `directory.css` (fellows/alumni, load more), `challengers.css` |

Fellows and alumni are the same page in two colours, so they are one component
with a `noun` and the colour from the page's body class (`--fellow`: red by
default, indigo under `.al`, GİRVAK ink under `.bt`).

The board is the same component with `variant="board"`, and it is the design's
page and nothing more: the hero, the cards and a link back to About (the
component's `after` slot) — **no filter bar, no search, no "load more"**, all
trustees on one page. Those are things the other directories have and the design
of this page does not, so they were left off. The back of a card says where the
person works instead of where they study. The page's words are written in the
page, not read from Airtable; the people and their count are the `people` table's.

The design draws `/board-of-trustees` with the About page's card grid (`.bcard`).
It takes the other directories' hero and flip cards instead, so the people pages
read as one. The
About page itself still shows its ten trustees, and the directors and team, in
the design's grid. Challengers is drawn differently in the design —
no photos, rows instead of cards — but its filter bar is the same.

## Data

- Fellows, alumni and challengers come from `GET /v1/content/people`
  (`people.fellows`, `.alumni`, `.challengers`), which maps the Airtable `people`
  table by its `tag` column. The tag `challlenger` (three l's) is what the base
  holds; the backend accepts it. Nothing is filtered on `onay` for these groups.
- Founders and ventures come from `GET /v1/content/ventures`. Both are gated on
  `onay`: a row an editor has not ticked is a draft and does not appear.
- The pages render every record into the HTML. The API never paginates them; the
  browser does (below).

## Filters

Every page follows the founders & ventures rule:

- Several values inside one dropdown **widen** the result (OR); different
  dropdowns **narrow** it (AND).
- A dropdown offers only the choices that would still return something, measured
  against the *other* filters but not its own. A choice the visitor has already
  selected always stays listed, so no filter is ever stuck on.
- When every choice in a dropdown is ruled out, its button dims (`is-exhausted`).
- Search folds case and Turkish letters (`fold`), so `ayse` finds `Ayşe`.

The bar has the same markup and the same place on all four pages: dropdowns at
the left, `clear filters` beside them, search at the right. What differs is from
the design and deliberate: the founders page sits its bar under the tabs, so it
has less space above; it alternates two accent colours where the others use one;
challengers prints cohorts as `2025` where the others print `’25`.

## Load more

The design shows everyone at once. With a few hundred portraits that is tens of
megabytes as the visitor scrolls (alumni: 376 photos of about 220 KB), so
`/fellows`, `/alumni` and `/challengers` (not the board, which is short and shows
everyone) reveal **24** at a time
(`PAGE_SIZE` in `pager.js`).

- Everything is in the HTML; the script only toggles `hidden`. A `hidden` card
  never fetches its `loading="lazy"` photo, which is the saving — the HTML is
  unchanged.
- Filters and search run over the **whole** list, not the revealed part. Any
  change to them starts again from the first 24.
- The photos are WebP (see `data-model.md`, `MediaAsset`): about 25 KB each, where
  the PNGs they replaced were about 225 KB. Together with the 24-at-a-time reveal
  the first screen of `/alumni` costs about 0.6 MB of portraits, down from 83 MB
  for a visitor who scrolled the whole list.
- The next 24 load by themselves when the end of the list comes within 300 px of
  the viewport (an `IntersectionObserver` on the block under the list), so the
  page scrolls on as one. The button stays: it is how a keyboard user asks for
  more, and all a browser without `IntersectionObserver` gets. After each load
  the observer is re-armed, so a short list or a tall screen keeps loading until
  the end is out of reach, and it stops when nothing is left.
- The footer is reached only after the list has loaded; the whole list is at most
  a few hundred entries, so that is a longer scroll, not an endless one.
- The button hides when nothing is left, and focus moves to the
  `aria-live` status line ("showing 48 of 405 alumni") so it is not dropped.
- Cards revealed by a click rise in one after another (`.lm-new`, reusing the
  `fvIn` keyframes); not under `prefers-reduced-motion`.
- Without JavaScript the whole list shows and there is no button.
- Challengers' yellow does not read as text on white, so its button stays ink and
  only the arrow turns yellow.

## URL

The current filter is kept in the address so a link opens the same view:
`?university=Ko%C3%A7%20%C3%9Cniversitesi&year=25&year=24&q=ayşe`. Repeated keys
widen a dropdown, as in the API. The URL is *replaced* on every change, not
pushed — a dropdown click is not a page the back button should visit — and the
"load more" count is not in it. Parameter order is fixed by the key list, so one
view is one URL.

## Tests

`npm test` runs `tests/pager.test.js` under `node --test`: the reveal arithmetic
and the URL round trip, which are pure functions with no dependencies. The
behaviour on a real page (filters, pruning, reveal, focus, URL) has no committed
test yet; it needs a DOM (`jsdom`) as a dev dependency.

## Running it locally

`astro.config.mjs` reads `API_BASE_URL` from `process.env` when the config loads,
which is **before** Astro reads `.env`. So a `.env` entry does not reach the
`/api` and `/media` proxy. If the API is not on port 8000, start the site with
the variable set:

```bash
API_BASE_URL=http://127.0.0.1:8001 npm run dev
```

Left unset, the proxy falls back to 8000 — and if something else is listening
there, every portrait 404s while the pages themselves still render.
