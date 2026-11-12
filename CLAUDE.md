# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Public website of GİRVAK (Entrepreneurship Foundation of Türkiye). Editors work only in Airtable; an edit shows up on the next page load with no build or deploy.

## Commands

One `.env` at the repo root serves the API, the site and docker compose (`cp .env.example .env`). Nested settings use `__` (`AIRTABLE__API_KEY`, `CONTENT__SOURCE`, …).

```bash
# backend (Python 3.12, uv)
cd backend && uv sync
uv run alembic upgrade head
uv run uvicorn girvak.main:create_app --factory --app-dir src --port 8000
uv run pytest                                   # all tests
uv run pytest -m "not db"                       # skip tests needing PostgreSQL
uv run pytest tests/modules/content/test_home.py::test_name   # single test
uv run ruff check src tests && uv run mypy      # mypy is strict on src/

# frontend (Astro 5 SSR, Node 20.9+)
cd frontend && npm install
npm run dev        # http://localhost:4321, reads ../.env
npm run check      # astro check (TypeScript strict)
npm test           # node --test on tests/**/*.test.js (pure browser-script helpers)

# deploy (on the VPS): TLS origin cert + nginx + docker compose (db, api, site)
sudo ./deploy/deploy.sh
```

## Architecture

```
Airtable → FastAPI (snapshot cache + /media mirror) → Astro SSR → nginx
```

- **Backend owns all content shaping.** `backend/src/girvak/modules/content/service.py` is the only way a page gets content. One module per page (`home.py`, `about.py`, `fellow.py`, `people.py`, `ventures.py`, `programs.py`, `apply.py`) maps Airtable rows to a Pydantic model in `schemas.py`. `fragments.py` holds the pure helpers for reading rows the way editors fill them: case-insensitive field aliases, families ordered by trailing number, attachments resolved to mirrored URLs.
- **Seeds are the fallback.** `modules/content/data/*.json` (loaded by `seeds.py`) is the committed copy of each page. It is served when `CONTENT__SOURCE` isn't Airtable, when a fragment is missing or renamed, or when Airtable is down. If you change a page's schema, update its seed JSON too.
- **Caching has three layers.**
  - The backend keeps an in-process snapshot per page (`infra/cache/snapshot.py`). It is warmed at startup. After the TTL expires it serves the stale copy while one rebuild runs in the background. A failed rebuild isn't retried for 30 s.
  - API responses carry ETag/304.
  - The frontend keeps a short in-process page cache (`frontend/src/lib/api.ts`), which also keeps serving the last good copy if the API fails.
  - `POST /v1/content/refresh` (admin key) drops the snapshot.
- **Media mirror.** `infra/storage/media_mirror.py` copies Airtable attachments to disk and serves them under `/media`, because Airtable URLs expire. Size variants are `full`, `large` (person cards) and `orig` (logos, to keep alpha).
- **Writes.** PostgreSQL holds only newsletter subscribers (`modules/newsletter`, Alembic migrations in `backend/migrations`). The frontend never writes to a database and never talks to Airtable.
- **Backend layout.** `config/settings.py` is where every env value, TTL, limit and secret name lives as a field on `Settings`. `http/` handles transport (request id, rate limit, security headers, errors). `infra/` holds adapters with no product logic. `modules/` holds product rules.
- **Frontend.** No UI framework. Pages in `src/pages/` fetch through `src/lib/api.ts` and render HTML on the server; the browser downloads no content JSON. Browser behaviour lives in plain JS under `src/scripts/`, with pure logic split out so it can be tested in `tests/`. `src/middleware.ts` sets the CSP: scripts must be bundled files, never inline `<script>`.

## Conventions

- Content is data, not code: a copy change should never require editing a `.astro` file. Some exceptions are deliberate, e.g. the board-of-trustees page text is written in the page.
- Airtable's shape is adapted to, never migrated. For example, the `people` tag `challlenger` (three l's) is accepted as-is.
- Source files start with a header block (`Module / Layer / Purpose / Dependencies / Called by / Calls`). Keep it accurate when you change a file's role.
- User-facing copy is Turkish. Ruff's RUF001–003 are disabled for that reason.
- Coding rules live in `.claude/rules/`, taken from the code as it ships (the old `coding-playbook` repository no longer exists):
  - `architecture.md`: always applies
  - `backend.md`: loaded for `backend/**`
  - `frontend.md`: loaded for `frontend/**`
  - `design.md`: loaded for Astro and CSS files

  If the shipped code and a rule disagree, fix the rule.
- The directory pages (`/fellows`, `/alumni`, `/challengers`, `/founders-ventures`, `/board-of-trustees`) share one filter bar, shuffle and load-more system. Read `docs/development/showcase-pages.md` before changing any of them.
- Some pages shuffle their order on every reload, so they send `Cache-Control: no-store`.

## Design language

For any visual frontend change (new section, page, component, style), use the `frontend-designer` agent (`.claude/agents/frontend-designer.md`). The full rules are in `.claude/rules/design.md`. In short:

- **Tokens only.** Colors, radii, shadows, easing and widths come from the `:root` variables in `frontend/src/styles/styles.css`. Don't introduce new hex values or fonts.
- **Brand.** Poppins is the only typeface. Turquoise `--turquoise` (#19BAD1) is the main color. Each program has its own color: fellow `--fellow` red, alumni `--alumni` indigo, challenger `--challenger` gold. Body text is in the `--ink` shades.
- **Headings.** Weight 500 (not 700), `--ink-800` color, negative letter-spacing, `text-wrap: balance`. Page hero H1 is `clamp(40px, 6.4vw, 75px)`. The headline's key word is *italic* in the accent color, and hero H1 letters change color on hover (`hero-letters.js`). Exact sizes are in the heading table in `design.md`. Plenty of whitespace (`.section`, `.wrap`). Uppercase eyebrow labels were removed by brand decision; don't bring them back.
- **Scoping.** Each page gets its own short body class and CSS prefix (`hm` home, `ab` about, `fp` fellow program, `fa`/`fl`/`al`/`bt`/`ca` directories…). A page's color comes from redefining a variable like `--fellow` under its body class.
- **Motion.** Use `--ease-out`/`--ease-soft` and scale by `--motion`. Every animation has a `prefers-reduced-motion` fallback. Hover effects go inside `@media (hover: hover)`.
- **Breakpoints.** Only the literals 480 / 768 / 1024 / 1280.

## Docs

- `docs/architecture/overview.md`: caching rules, decisions, out-of-scope items
- `docs/data-model.md`
- `docs/api.md`
- `docs/development/setup.md`
- `docs/operations/deployment.md`

The previous static Astro + SQLite version is at commit `a927f30` (`git worktree add ../girvak-old a927f30`).
