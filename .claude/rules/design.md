---
paths:
  - "frontend/src/**/*.astro"
  - "frontend/src/styles/**"
  - "frontend/src/components/**"
  - "frontend/src/scripts/**"
---

# Design language

Every value below is measured from the shipped CSS. Consistency beats novelty. Before you build, find the closest existing page or component and copy its pattern: class names, spacing and structure. If you must deviate, say so and give a reason.

## Tokens (`frontend/src/styles/styles.css` `:root`)

Use only tokens. Don't add raw hex colors, new fonts or arbitrary shadows. Older CSS hard-codes `#373d42` and `#19bad1`; in new code write `var(--ink-800)` and `var(--turquoise)`.

- **Brand:**
  - `--turquoise` #19BAD1, with the scale `-600/-400/-200/-100/-050`
  - Semantic aliases: `--accent`, `--accent-press`, `--accent-soft`, `--accent-wash`
- **Program colors:**
  - `--fellow` red #BA1818
  - `--alumni` indigo #281858
  - `--challenger` gold #F7BE10
  - Also `--deep-teal` and `--sand`
- **Secondary accents:** `--teal`, `--coral`, `--yellow`, `--mint`, `--navy`. Use them only for borders, highlights and micro-interactions, never large fills. On the home page they're applied via `.acc-*`, which sets `--c`.
- **Neutrals:**
  - **Headings are `--ink-800` (#373D42)**, not pure ink
  - Body text `--fg-2`, muted text `--fg-3`
  - `--border`
  - Background white (about hero `#fafbfc`)
- **Radius:** `--r-xs` 6 · `--r-sm` 12 · `--r-md` 18 · `--r-lg` 28 · `--r-xl` 40 · `--r-pill`
- **Shadows:** `--shadow-1/2/3`. `--shadow-brand` is reserved for primary buttons.

## Heading scale (what the pages actually use)

All text is Poppins (300–800, italic 500), with no other typeface. **The standard heading weight is 500, not 700.** The global `.h1` (700) and `.display` classes are legacy; page headings don't use them.

| Role | Size | Weight | Line-height | Letter-spacing | Used in |
|---|---|---|---|---|---|
| **Page hero H1** (default) | `clamp(40px, 6.4vw, 75px)` | 500 | 1.04 | -0.035em | `.fa-hero-title`, `.fv-hero-title`, `.ap-hero-title`, `.pp-h1` |
| Hero H1, home | `clamp(40px, 5.2vw, 75px)` | 500 | 1.08 | -0.035em | `.hero3-title` |
| Hero H1, fellow program | `clamp(38px, 5.1vw, 71px)` | 500 | 1.08 | -0.035em | `.fhero-h1` |
| Hero H1, compact page | `clamp(36px, 5vw, 56px)` | 500 | 1.04 | -0.04em | `.ab-hero-title--page` |
| **Hero subtitle** | `clamp(15px, 1.28vw, 19px)` (directories: 20px) | 400 | 1.5 | 0 | `.fa/.fv/.ap-hero-sub`. Top margin `clamp(28px, 3.4vw, 46px)`, `text-wrap: pretty` |
| **Section H2** | `clamp(26px, 3.4vw, 38px)` | 500 | 1.08 | -0.03em | `.impact-title`, `.ab-story-head h2`, `.h2` |
| Large H2 (photo band, feature) | `clamp(28–30px, 3.6vw, 52px)` | 500 | 1.08–1.12 | -0.03em | `.ab-photo h2`, fellow sections |
| Section heading with subtitle | `clamp(26px, 3vw, 40px)` | 500 | 1.1 | -0.03em | `.ap-shead-h` |
| Small H2 (sub-block) | `clamp(22–24px, 2.8–3.2vw, 27–30px)` | 500 | — | -0.03em | `.ab-work-copy h2`, `.people-head h2` |
| Popup title | `clamp(22px, 2vw, 28px)` | 500 | 1.15 | -0.03em | `.cp-title` |
| **Card title** | `clamp(17px, 1.35–1.5vw, 20–22px)` | 700 | 1.1–1.2 | -0.015 to -0.02em | `.ap-card-title`, `.fv-vname` |
| Big number / year | `clamp(30px, 2.6vw, 42px)` | **300** | 1 | -0.01em | years on cards, fellow stats |
| Body | 17px (long text `clamp(16px, 1.4vw, 18.5px)`) | 400 | 1.6–1.68 | 0 | `--fg-2` |
| Small / meta | 14.5px, tiny labels `clamp(11px, 1vw, 12.5px)` | 400–500 | 1.3–1.55 | — | `--fg-3` |

- **Hero H1s:**
  - Use `text-wrap: balance` and `margin: 0` (home and fellow use `margin-left: -5px` for optical alignment).
  - Keep the accent clause together with `white-space: nowrap`, except under 480px.
- **Signature:** the key word or clause of a headline is ***italic* in the page accent color**, once per headline. In directories the hero's italic `<i>` is `--fellow`. Elsewhere it's turquoise (or `.partners-hl` coral on the home partners heading).
- **No uppercase eyebrow / overline labels.** They were removed site-wide by brand decision.

## Hover patterns (reuse one of these; don't invent a new one)

Put every hover effect inside `@media (hover: hover)`. Give links the same effect on `:focus-visible`.

1. **Hero letter hover (signature).**
   - `scripts/hero-letters.js` (directories, apply) or `pp-heading.js` (programs) splits the H1 into one span per letter. Plain letters are `.ch`; letters inside the italic `<i>` are `.ch-inv`.
   - `.ch:hover` → page accent (`--turquoise`, or `--fellow` on directories and the fellow page).
   - `.ch-inv:hover` → `--ink-800` (the accent word inverts back to ink).
   - Transition: `color .3s var(--ease-out)`.
   - Every page hero H1 gets this. Import the script, don't copy it.
2. **Text CTA with hand-drawn arrow** (`.h3btn`, "see all", "load more"):
   - Link text 500, `clamp(20px, 2.1vw, 27–30px)`, `--ink-800`, letter-spacing -0.4px.
   - The arrow is `.cta-arrow`, a mask of `/images/cta-arrow.png` filled with `currentColor`.
   - Hover: color → accent, arrow `translateX(7px)`, `.25s var(--ease-out)`.
   - "Load more" rotates the arrow: `rotate(90deg) translateX(7px)`.
   - This is the site's main link style; prefer it over `.btn` in editorial sections.
3. **Card lift:** `translateY(-4px)` (people cards `-5px`) plus `box-shadow: var(--shadow-2)`.
4. **Flip card:** `.fv-inner` / `.fcard-inner` → `rotateY(180deg)` showing details on the back (see `ventures.css`, home fellows belt).
5. **Image zoom inside a card:** `img { transform: scale(1.04) }`, clipped by the card's `overflow: hidden`.
6. **Small controls:**
   - Social and icon buttons: `translateY(-2px)` plus a color fill.
   - Close ✕: `rotate(90deg)`.
   - Inline small arrows: `translateX(3–5px)`.
7. **Buttons:** `.btn-*`, a lift of `translateY(calc(-2px * var(--motion)))`, and the `.ico` arrow slides 4px.

**Durations:** hover color and transform `.2–.3s` (`.25s` and `.3s` are the defaults); menus and reveals `.35–.6s`; scroll reveal `.8s var(--ease-soft)`.

## Page dimensions

- **Horizontal edge:** most pages are full-bleed with `--edge: clamp(20px, 5vw, 80px)`, set on the page class. The same value appears as `.ap-edge` and as the nav padding. The older `.wrap` / `--gutter` (max 64px) is for centered legacy sections.
- **Max widths:**
  - Centered content blocks: `1180px`
  - Global `--maxw`: `1240px`
  - Readable text: `760px` / `46–60ch`
  - Hero H1 blocks: `16–20ch` on about pages
- **Hero top padding** clears the fixed nav:
  - Standard: `clamp(140px, 15vw, 190px)` (apply, directories, ventures). Programs uses `clamp(130px, 15vw, 190px)`
  - About: `clamp(130px, 15vw, 180px)`
  - Compact page: `clamp(120px, 14vw, 160px)`
  - Hero bottom:
    - Directories and ventures: `clamp(20px, 2.4vw, 32px)`, since a filter bar follows
    - Apply: `clamp(28px, 3.4vw, 46px)`
    - Programs: `clamp(34px, 4vw, 56px)`
- **Section vertical padding:**

  | Section type | Padding |
  |---|---|
  | Standard | `clamp(56px, 7vw, 96px)` |
  | Large | `clamp(72px, 9vw, 128px)` |
  | Content block | `clamp(48px, 6vw, 86px)` |
  | Last section before footer | `clamp(64–70px, 8vw, 112–120px)` |

- **Grids:**
  - Card gaps `clamp(10–12px, 1.1–1.5vw, 18–22px)`
  - Two-column blocks gap `clamp(28px, 5vw, 72px)`
  - Card padding `clamp(16px, 1.7vw, 24px)`
- **Photo band:** `min-height: clamp(420px, 52vw, 640px)`.
- **Breakpoints:** the literals **480 / 768 / 1024 / 1280**, plus **1600** for very wide screens (`max-width` queries are the norm below, `min-width: 1600px` above). Older sheets use a few in-between values (420–460, 520, 560, 680, 780, 820, 900, 940, 1100); don't add more, and move to the literals when you touch them.
- **Card grids** step down one column at a time and end at one column on phones:
  - Directories and ventures: 4 → 3 (≤1100) → 2 (≤780) → 1 (≤460); one more column from 1600
  - Challenger cards: 5 → 4 → 3 → 2 → 1
  - Apply: 4 → 3 → 2 → 1; programs: 3 → 2 → 1; stats: 4 → 2 → 1; partner logos: 4 → 2
  - Two-column blocks (about, program page) become one column at 768
- **Very wide (1600+):** content stays full-bleed with the `--edge` margin; add a column rather than letting cards grow, and don't cap the width on one section only (the nav and heroes would misalign).
- **Touch screens:** hover effects live inside `@media (hover: hover)`; the content a hover reveals must also be reachable by tap (flip cards flip on focus/tap, the menu opens as an accordion).
- Check the result at ~375px (mobile) with no horizontal scroll, plus 768, 1280 and 1920.

## Page scoping and color

- **Body class:** each page sets one in `BaseLayout`.
- **CSS prefix:** each page's CSS uses a short prefix:
  - `hm` home/base
  - `ab` about
  - `fp` fellow program
  - `ap` apply
  - `pp` programs
  - `fv`/`fa` directories
  - `fl` fellows, `al` alumni, `bt` board, `ca`/`cr` challengers
- New pages get a new short prefix, their own stylesheet in `src/styles/`, and their own `--edge`.
- **Recolor by redefining a variable** under the body class (e.g. `.al { --fellow: var(--alumni) }`). Don't fork rules.
- **Text selection** takes the page color. Keep contrast readable: ink or grey text on gold, white on red and indigo.

## Components

- **Buttons:** `.btn` with `-primary`, `-dark`, `-ghost` or `-inverse`, plus `-lg` for size.
- **Chips:** `.chip`.
- **Directories:** reuse `PeopleDirectory.astro`, `ventures.css` and `directory.css`. Read `docs/development/showcase-pages.md` first.
- **Stat cards:** white, `--r-md`, `--shadow-2`, with a 4px bottom border in `var(--c)` (`.ab-stat`).
- **Focus:** keep the global turquoise `:focus-visible` ring.

## Motion

- Easing: `--ease-out` for UI, `--ease-soft` for reveals. Distances scale by `var(--motion)`.
- Scroll reveal uses `.reveal`/`.rv` + `.in`.
- Every animation needs a `@media (prefers-reduced-motion: reduce)` fallback.
- **Page transitions** are the browser's cross-document view transition (`@view-transition` in `styles.css`, only under `prefers-reduced-motion: no-preference`): the old page stays opaque while the new one fades and rises (`pt-rise`, .62s `--ease-soft`); the fixed nav is its own layer and is not cross-faded. No JS, no `ClientRouter` (the pages' own scripts and the CSP rely on full loads). Don't add a `view-transition-name` to anything else without checking it against every page.

## Images

- Variants come from the API: `large` for person cards, `full` for section imagery, original for logos.
- Use `loading="lazy"` below the fold and keep the existing aspect ratios (challenger cards 3:2).
