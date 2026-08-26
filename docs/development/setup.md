# Local setup

Two processes: the API on 8000, the site on 4321. The site reads the API; the API
reads Airtable (or the committed seed).

## Requirements

- Python **3.12** — pinned in `backend/pyproject.toml` (`requires-python`)
- [uv](https://docs.astral.sh/uv/) for dependencies and the virtualenv
- Node.js **20.9+** — pinned in `frontend/.nvmrc` and `package.json` `engines`
- PostgreSQL **13+** — `gen_random_uuid()` is used as a column default
- Airtable personal access token with `data.records:read` on the content base

## Backend

```bash
cd backend
uv sync                 # installs from the committed uv.lock
cp .env.example .env
```

Fill in `.env`:

| Name | What it is |
|---|---|
| `ENVIRONMENT` | `local` |
| `ADMIN_API_KEY` | any long random string; required, no default |
| `DATABASE__DSN` | `postgresql+asyncpg://girvak:girvak@127.0.0.1:5432/girvak` |
| `CONTENT__SOURCE` | `seed` to work offline, `airtable` for live content |
| `AIRTABLE__API_KEY` / `AIRTABLE__BASE_ID` | required when the source is `airtable` |

Every name is listed in `backend/.env.example`. Unknown names fail the boot on
purpose (`extra="forbid"`), so a typo in a deploy variable cannot go unnoticed.

Database:

```bash
docker run -d --name girvak-pg \
  -e POSTGRES_USER=girvak -e POSTGRES_PASSWORD=girvak -e POSTGRES_DB=girvak \
  -p 5432:5432 postgres:17
uv run alembic upgrade head
```

Run it:

```bash
uv run uvicorn girvak.main:create_app --factory --app-dir src --port 8000
# behind a proxy in production, add: --proxy-headers --forwarded-allow-ips="*"
```

`http://127.0.0.1:8000/health` answers without touching the database.
Set `DOCS_ENABLED=true` locally for `/docs`.

## Frontend

```bash
cd frontend
npm install
cp .env.example .env      # API_BASE_URL=http://127.0.0.1:8000
npm run dev               # http://localhost:4321
```

The dev server proxies `/api` and `/media` to the API, which is how production
serves them too — so the browser never learns the API's hostname.

Production-style check:

```bash
npm run build && npm start        # node ./dist/server/entry.mjs
```

`npm start` serves only the site: `/api` and `/media` come from the reverse
proxy, so the newsletter form and CMS images need nginx (or `npm run dev`).

## Test data

`CONTENT__SOURCE=seed` serves the committed copy in
`backend/src/girvak/modules/content/data/` — enough to develop every page with no
Airtable access. The newsletter form needs PostgreSQL; nothing else does.

## Common setup failures

| Symptom | Cause |
|---|---|
| `ValidationError` naming `environment`, `admin_api_key`, `database` at boot | `.env` missing or a required name unset |
| `error parsing value for field "cors_origins"` | comma-separated is fine; a stray `[` is not |
| Pages return 500 and the log says `AbortError` | the API is not running, or `API_BASE_URL` points at the wrong port |
| `alembic upgrade head` cannot connect | PostgreSQL is not up, or `DATABASE__DSN` is wrong |
| CMS images 404 in `npm start` | `/media` is served by the API through the proxy, not by the site |
| Images do not optimise | `sharp` needs its native binary; allow its install script |

MUST NOT: put secret values in this file. `.env.example` holds names only.
