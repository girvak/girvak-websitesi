# GİRVAK Website

Public site of the Entrepreneurship Foundation of Türkiye. Content lives in
Airtable; the site shows it on the next page load — no build, no deploy.

## What it is for

Four pages — home, about, fellow program, board of trustees — plus a newsletter
form. Editors work in Airtable and never touch this repo.

## Architecture in a few lines

```
Airtable → FastAPI (snapshot cache + /media mirror) → Astro SSR → nginx
```

FastAPI reads Airtable at most once per TTL and can be told to re-read now.
Astro renders each page per request from that API, so an edit appears on reload.
Details: [docs/architecture/overview.md](docs/architecture/overview.md) ·
[docs/data-model.md](docs/data-model.md).

## Stack

- **backend/** — Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 + Alembic, PostgreSQL
- **frontend/** — Astro 5 SSR (`@astrojs/node`), TypeScript strict, no UI framework
- **coding-playbook/** — the architecture and coding rules both of the above follow
- **old/** — the previous site, kept for reference. Nothing here reads it

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js 20.9+
- PostgreSQL 13+ (only the newsletter form needs it)
- An Airtable personal access token with read access to the content base

## Local setup

Full instructions: [docs/development/setup.md](docs/development/setup.md).

```bash
# backend
cd backend && uv sync && cp .env.example .env   # fill ADMIN_API_KEY, DATABASE__DSN
uv run alembic upgrade head
uv run uvicorn girvak.main:create_app --factory --app-dir src --port 8000

# frontend
cd frontend && npm install && cp .env.example .env
npm run dev            # http://localhost:4321
```

## How to run the tests

```bash
cd backend && uv run pytest            # add -m "not db" to skip the ones needing PostgreSQL
cd backend && uv run ruff check src tests && uv run mypy
cd frontend && npm run check
```

More: [docs/development/testing.md](docs/development/testing.md) once it exists.

## Repository layout

```
backend/     FastAPI: content API, newsletter, Airtable adapter, media mirror
frontend/    Astro SSR: four pages, layouts, styles, browser behaviour
docs/        architecture, data model, setup, API
coding-playbook/  the rules; read AGENTS.md if you are an AI coding agent
old/         previous implementation, reference only
```

## Deploy

Host nginx in front of two containers plus PostgreSQL; nginx forwards `/api` and
`/media` to the backend. Steps, configuration names, rollback and post-deploy
checks: [docs/operations/deployment.md](docs/operations/deployment.md).

## Documentation

- [docs/architecture/overview.md](docs/architecture/overview.md) — how the system works
- [docs/operations/deployment.md](docs/operations/deployment.md) — building, deploying, rolling back
- [docs/data-model.md](docs/data-model.md) — the nouns and who owns them
- [docs/api.md](docs/api.md) — the HTTP contract
- [docs/development/setup.md](docs/development/setup.md) — running it locally

## Who to ask

GİRVAK — enes@girisimcilikvakfi.org
