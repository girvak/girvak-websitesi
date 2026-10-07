# Showcase pages

`/founders-ventures`, `/fellows`, `/alumni`, `/challengers` and
`/board-of-trustees` are the site's directories: a hero and a list of people or
ventures, and — on all but the board — a filter bar. They share one filter bar and
one set of behaviours, so a change to it is a change to all of them. This page says where each piece lives and which rules are deliberate.

## Where things are

| Piece | File |
|---|---|
| Fellows, alumni and trustees body (hero, filter bar, cards) | `src/components/PeopleDirectory.astro` |
| Challengers page (the same component, photo-less cards) | `src/pages/challengers.astro` |
| Founders & ventures page (two tabs) | `src/pages/founders-ventures.astro` |
| Shared filter bar behaviour | `src/scripts/filters-multi.js` — `wire`, `wireSearch`, `pruneOptions`, `fold`, `hits` |
| "Load more" reveal | `src/scripts/load-more.js` |
| Reveal arithmetic and the filter ↔ URL round trip (pure) | `src/scripts/pager.js` |
| Hero headline letter effect | `src/scripts/hero-letters.js` |
| Page scripts | `directory.js` (fellows, alumni, challengers, board), `ventures.js` |
| Styles | `ventures.css` (shell, filter bar, cards), `directory.css` (fellows/alumni, load more), `challengers.css` (the challenger cards) |

Fellows and alumni are the same page in two colours, so they are one component
with a `noun` and the colour from the page's body class (`--fellow`: red by
default, indigo under `.al`, GİRVAK ink under `.bt`).

Selected text (Ctrl+A, dragging) takes the page's full colour: alumni indigo and
fellows red with white text, challengers yellow with GİRVAK grey text (white on
that yellow would not read). The fellow program page keeps its own softer tints
(`fellow.css`). `fellows.astro` carries its own body class (`fl`) so the rule does
not reach the other pages.

The board is the same component with `variant="board"`, and it is the design's
page and nothing more: the hero, the cards and a link back to About (the
component's `after` slot) — **no filter bar, no search, no "load more"**, all
trustees on one page. Those are things the other directories have and the design
of this page does not, so they were left off. The back of a card says where the
person works instead of where they study. The page's words are written in the
page, not read from Airtable; the people are the `people` table's. The headline's
italic word and its hover are turquoise like the About hero, though the cards are
ink (`.bt` sets `--fellow` to ink, so the hero overrides it — left alone, both the
accent and the hover would be the same ink as the text around them).

The design draws `/board-of-trustees` with the About page's card grid (`.bcard`).
It takes the other directories' hero and flip cards instead, so the people pages
read as one. The
About page itself still shows its ten trustees, and the directors and team, in
the design's grid.

Challengers is the same component too, drawn the design's "grey rectangle cards"
way (`All Challengers -grey rectangle cards-`): no photos, smaller 3:2 rectangles
five to a row, grey in front with the name and yellow behind with the university
and department. The earlier list version of the page (rows with a hand-drawn rule
under each) is gone. `challengers.css` sets the page's accent by giving `.fa.ca`
`--fellow: var(--chal)`, so everything `directory.css` colours with the accent is
yellow; its card rules are written `.fa.ca …` / `.fa.cr …` so they win over
`directory.css`'s `.fa …` at the same weight whatever order the sheets load in.

## Data

- Fellows, alumni and challengers come from `GET /v1/content/people`
  (`people.fellows`, `.alumni`, `.challengers`), which maps the Airtable `people`
  table by its `tag` column. The tag `challlenger` (three l's) is what the base
  holds; the backend accepts it. Nothing is filtered on `onay` for these groups.
- Founders and ventures come from `GET /v1/content/ventures`. Both are gated on
  `onay`: a row an editor has not ticked is a draft and does not appear.
- The pages render every record into the HTML. The API never paginates them; the
  browser does (below).

## Order

`/fellows`, `/alumni` and `/challengers` — and the three belts on the fellow
program page — show people in a **new random order on every reload**
(`src/lib/shuffle.ts`), so nobody is stuck at the end of an alphabet. The belts also
pick their 40 at random. It happens in the page, not the API: the API's payload stays
identical, so its ETag still earns a 304. A page that shuffles says
`Cache-Control: no-store`, or a browser would reuse one shuffle for the next 30
seconds of reloads; the API response behind it is still cached, so this costs a
render, not a round trip. The dropdowns are not shuffled: years newest first, the
rest A–Z. The board, the home page and the ventures list keep their order (the
founders tab on `/founders-ventures` has its own shuffle).

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
challengers prints the year dropdown as `2025` where the others print `’25` (the
cards themselves all print `’25`).

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
- The button hides when nothing is left, and focus moves to the `aria-live` status
  line so it is not dropped. That line ("showing 48 of 405 alumni") is visually
  hidden: **no record count is shown anywhere on the site** — not how many people
  there are, nor how many are loaded — and a screen reader is the only thing that
  is told.
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

A link can also open `/founders-ventures` already filtered, with the same slugs
the API's filters use: `?program=tskb-co-venture#ventures` (repeat a key to widen
it; `sector`, `program` and `year` are read). A value that is not an option on the
page is dropped, so a link to something the base does not have shows everyone. The
A deep link such as `?program=founder-one` starts to filter the directory the
day the `programs` table has a "Founder One" row.

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
