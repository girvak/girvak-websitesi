# GİRVAK Website

Modern client–server rebuild of the GİRVAK (Entrepreneurship Foundation of Türkiye) site.

- **Frontend** — [Astro](https://astro.build) (static SSG, optimized for SEO + speed). `frontend/`
- **Backend** — [FastAPI](https://fastapi.tiangolo.com) (content API + newsletter). `backend/`

Phase 1 ships the **home page**. About / Fellow Program / Board of Trustees follow in Phase 2.

## Architecture

```
Astro (build time)  ──GET /api/content/home──►  FastAPI  ──►  content seed JSON
   │                                                            (Airtable-shaped,
   └─ newsletter form ──POST /api/newsletter──►  FastAPI  ──►   adapter swaps to Airtable later)
                                                       └──►  SQLite (subscribers)
```

Content is decoupled from code: the FastAPI `content_source` adapter reads an
Airtable-shaped seed (`backend/app/data/home_content.json`) today, and can be
switched to a live Airtable base by env without touching the frontend.

## Run locally

### 1. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Content:  http://localhost:8000/api/content/home

### 2. Frontend (Astro)

```bash
cd frontend
npm install
cp .env.example .env
npm run dev          # http://localhost:4321
```

`npm run build && npm run preview` produces the static site. If the backend is
down at build time, Astro falls back to the bundled snapshot in
`frontend/src/data/home_content.json` (keep it in sync with the backend seed).

## Images

Design assets live in the Claude Design project and belong in
`frontend/public/images/` and `frontend/public/assets/`. Until they're added,
image slots render empty but the layout is intact.

> Performance upgrade path: move hero/card photos into `frontend/src/assets/`
> and switch `<img>` → Astro's `<Image />` for automatic WebP/AVIF + `srcset`.

## Airtable content (CONTENT_SOURCE=airtable)

The backend reads Airtable via REST using your Personal Access Token. Set in
`backend/.env`:

```
CONTENT_SOURCE=airtable
AIRTABLE_API_KEY=pat...        # token with data.records:read on the base
AIRTABLE_BASE_ID=app...
```

The adapter is **seed + overrides**: it starts from the bundled seed and
overrides each section Airtable provides. A missing/empty table keeps the seed
value, so you can fill the base incrementally. Field names are matched
case-insensitively with aliases.

Expected tables (names overridable via `AIRTABLE_TABLE_*` env):

| Table | Fields (aliases accepted) |
|---|---|
| `Settings` | `Key`, `Value` — singleton text. Keys: `seo_title`, `seo_description`, `hero_base_text`, `hero_rotator_words` (comma-sep), `hero_subhead_pre/_highlight/_post`, `partners_headline_pre/_highlight`, `partners_sub`, `footer_newsletter_title/_text`, `footer_brand_text`, `footer_address/_email/_phone/_phone_href`, `footer_copyright` |
| `HeroImages` | `Order`, `Image` (attachment) |
| `Impact` | `Order`, `Count`, `Decimals`, `Prefix`, `Suffix`, `Label`, `Description`, `Color` (teal/coral/ink), `Row`, `Col` |
| `WhatWeDo` | `Order`, `Lead`, `Sub`, `Eyebrow`, `Text`, `Color`, `Image`, `Href` |
| `Fellows` | `Order`, `Year`, `Name`, `University`, `Image`, `Color` |
| `Partners` | `Order`, `Name`, `Logo` (attachment), `Featured` (checkbox) |

CTAs, nav menu and footer Explore links stay in code (structural).

After editing Airtable, `POST /api/content/refresh` clears the server cache (or
restart). Rebuild the frontend to regenerate the static pages.

## Deploy (Phase 2+)

- Frontend → any static host (Vercel / Netlify / Cloudflare Pages). Set
  `PUBLIC_SITE_URL`, `API_BASE_URL`, `PUBLIC_API_BASE_URL`.
- Backend → Render / Railway / a VPS (or `docker-compose up backend`).
