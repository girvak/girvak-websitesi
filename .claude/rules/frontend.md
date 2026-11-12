---
paths:
  - "frontend/**"
---

# Frontend rules (Astro 5 SSR, TypeScript strict, no UI framework)

Visual and design rules are in `.claude/rules/design.md`. Use the `frontend-designer` agent for visual work.

## Structure

- **Pages** (`src/pages/*.astro`) fetch on the server through `src/lib/api.ts`, then render. The HTML arrives filled in; the browser never downloads content JSON.
- **`src/lib/api.ts`** is the only way to reach the backend. It holds a short in-process cache per path, keeps the last good copy when the API fails, and has a 5 s timeout. Add a getter here for any new endpoint, and keep API types in `src/lib/types.ts` matching the backend Pydantic schemas.
- **`src/lib/env.ts`** is the only place that reads env. Values are read at request time, so a domain change is a restart, not a rebuild.
- **Layout:** every page uses `layouts/BaseLayout.astro` with a `title`, `description` and its `bodyClass`.
- **Components** go in `src/components/`, with feature subfolders (`about/`, `fellow/`) when a component belongs to one page.

## Browser scripts

- Plain JS modules in `src/scripts/`, one per page plus shared ones (`filters-multi.js`, `load-more.js`, `card-fill.js`).
- **No inline `<script>` code.** The CSP is `script-src 'self'`, so scripts must be bundled files.
- **Split pure logic from DOM code.** Arithmetic and parsing go in a DOM-free module (like `pager.js`) with JSDoc types and a test in `frontend/tests/*.test.js` (`node --test`).
- Reuse the shared helpers rather than copying them: `fold` for Turkish-insensitive search, `wire`/`pruneOptions` for filters, `shuffle.ts` for random order.
- In-page scrolling (tabs, panels, "jump to") goes through `scrollToTop(el)` in `scroll-to.js`. It measures the fixed nav each time and re-checks once the scroll ends. Don't hard-code a header offset; the nav's height changes with the viewport.
- Progressive enhancement: the page must be readable before the script runs. Load more works by toggling `hidden`, not by fetching.

## Things not to add

- React, Vue, Svelte, Tailwind, or CSS-in-JS
- A client-side data fetch for content
- A third-party script or tracker
- A new external origin, because the CSP lists every one (`middleware.ts`)

## Before finishing

```bash
cd frontend && npm run check && npm test
```
