# Deployment

How the site is published, and how to publish it again. Audience: whoever
operates the server.

Layout on the host — unchanged from the previous deployment, so the nginx site
file is the only thing that has to be replaced:

| Port | Serves |
|---|---|
| **80 / 443** | host nginx, the public entry point |
| 127.0.0.1:**8082** | backend API (container) |
| 127.0.0.1:**8083** | site, Astro SSR (container) |
| 127.0.0.1:**5432** | PostgreSQL (container, loopback only) |

nginx owns routing: `/` to the site, `/api/…` to the backend with the `/api`
prefix stripped, `/media/…` to the backend with immutable caching. **The site does
not proxy anything itself** — without nginx (or `npm run dev`), `/api` and
`/media` are 404. That is deliberate: one place decides routing.

## Migrating from the previous deployment

The server already runs the old site with nginx, DNS and certbot configured, and
the port layout above is unchanged — so **DNS and the certificate need nothing**.

The mandatory change is one character. The old API served its routes under
`/api/...`, so nginx passed the path through:

```nginx
location /api/ { proxy_pass http://127.0.0.1:8082; }     # old: path kept
location /api/ { proxy_pass http://127.0.0.1:8082/; }    # new: /api stripped
```

The new API serves `/v1/...`, so without that trailing slash every API call
becomes a 404 and the newsletter form stops working. `/media/` and `/` are
unchanged.

Two ways to apply it:

- **Minimal (keeps certbot's work).** Edit the live file
  `/etc/nginx/sites-available/girvak`, add the trailing slash, and drop the three
  `add_header` security lines — the app sends those itself now, and nginx would
  send each one twice. Then `sudo nginx -t && sudo systemctl reload nginx`.
- **Replace the file.** Copy `deploy/nginx-site.conf` over it, then re-run
  `sudo certbot --nginx -d girisimcilikvakfi.org -d www.girisimcilikvakfi.org`,
  because the copy removes the TLS blocks certbot had written.

Also on the server, once:

- `frontend/dist` is no longer mounted anywhere: the site is a Node process now,
  not a static bundle behind an nginx container. `deploy/frontend-container.conf`
  and `deploy/frontend.env.production` from the old repo are obsolete.
- The published ports now bind to `127.0.0.1` instead of every interface, so
  `:8082` and `:8083` are no longer reachable from outside the host.
- `docker compose up -d --build` recreates the `backend` and `frontend` services
  in place and adds `db`.
- Import the legacy subscriber file (below) before announcing the form.

## Environments

- **local** — `uv run uvicorn …` + `npm run dev`. `CONTENT__SOURCE=seed` works
  with no Airtable access at all.
- **production** — the three containers plus host nginx, on the VPS.

There is no staging today. When one appears it is this file plus a second nginx
site; nothing in the images changes, because no environment value is baked in.

## Build

```bash
docker compose build          # backend + site images
```

Both images are digest-pinned. Upgrading a base image is an edit to the
`Dockerfile`, visible in the diff — never a silent pull.

The site image bakes **no** configuration: `src/lib/env.ts` reads the environment
at request time, so one image serves any environment and changing a value is a
restart, not a rebuild.

## Configuration

Names only; values live in `backend/.env` on the server and in the compose file's
environment blocks.

| Where | Required names |
|---|---|
| `backend/.env` | `ADMIN_API_KEY`, `AIRTABLE__API_KEY`, `AIRTABLE__BASE_ID`, `CONTENT__SOURCE=airtable` |
| beside `docker-compose.yml` (`.env`) | `POSTGRES_PASSWORD` |
| compose `backend` | `ENVIRONMENT`, `DATABASE__DSN`, `TRUSTED_HOSTS`, `CORS_ORIGINS`, `MEDIA__DIR_PATH` |
| compose `frontend` | `API_BASE_URL`, `PUBLIC_API_BASE_URL` (empty), `PUBLIC_SITE_URL` |

MUST NOT: a secret value in `docker-compose.yml`, in this file, or in any file
under `docs/`. `.env` is git-ignored; `.env.example` carries the names.

## Deploy

```bash
git pull
docker compose build
docker compose run --rm backend alembic upgrade head    # see Database, below
docker compose up -d
sudo cp deploy/nginx-site.conf /etc/nginx/sites-available/girvak
sudo ln -sf /etc/nginx/sites-available/girvak /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Order matters: migrate before the new containers serve traffic; reload nginx last,
once both upstreams answer.

TLS: `sudo certbot --nginx -d girisimcilikvakfi.org -d www.girisimcilikvakfi.org`
rewrites this site file to listen on 443 and redirect 80. Re-copying the file
overwrites that, so run certbot again (it is idempotent) after replacing it.

## Database migration

Migrations are a **release step**, never a container entrypoint: two starting
replicas would race each other.

```bash
docker compose run --rm backend alembic upgrade head
```

The chain is backward compatible by rule (`coding-playbook/python-fastapi-backend/07-migrations.md`),
so the old code keeps working against the new schema during a rolling restart.

The previous site kept subscribers in a SQLite file. That file is preserved
locally at `backend/legacy-subscribers.db` (git-ignored, because it holds real
addresses). Import it into PostgreSQL once, before or just after the first
release — one `INSERT ... ON CONFLICT DO NOTHING` per row is enough, and the
unique constraint makes a re-run harmless.

Only `newsletter_subscribers` lives in PostgreSQL. Content is Airtable's, and the
`/media` mirror is a cache — losing either costs a re-read, not data.

## Content, after deploy

Content does not ship with a release. An editor changes Airtable and the next page
load shows it, within `CONTENT__TTL_SECONDS` (default 600). To publish immediately:

```bash
curl -X POST -H "X-Admin-Token: $ADMIN_API_KEY" https://girisimcilikvakfi.org/api/v1/content/refresh
```

Each API container holds its own snapshot, so with more than one backend replica
the call must reach each of them — or wait out the TTL.

A cold `/media` mirror does not slow a deploy: the first render hands out
Airtable's own URLs and the files download in the background (measured: a full
mirror is ~650 files / ~140 MB and fills in about twenty seconds).

## Rollback

```bash
git checkout <previous tag or commit>
docker compose build && docker compose up -d
```

Rolling the schema back is a **new revision**, not `alembic downgrade` against
production data. `downgrade()` exists for local work.

The `backend_media` volume survives both directions; nothing has to be restored.

## Release process

1. Merge to `main`, tag it.
2. Deploy as above.
3. Run the checks below.
4. Record what shipped in `CHANGELOG.md` (user-visible changes only).

## CI/CD

Not wired yet. When it is, it runs what a developer runs locally, in this order:
`uv sync --frozen` → `ruff check` → `mypy` → `pytest` → dependency audit, and for
the site `npm ci` → `astro check` → `npm run build`.

MUST NOT: a pipeline that migrates production without a human step.

## Checks after deploy

```bash
curl -fsS https://girisimcilikvakfi.org/api/health                       # {"status":"ok"}
curl -fsS -o /dev/null -w '%{http_code}\n' https://girisimcilikvakfi.org/
curl -fsS -o /dev/null -w '%{http_code}\n' https://girisimcilikvakfi.org/about
curl -fsS -o /dev/null -w '%{http_code}\n' https://girisimcilikvakfi.org/fellow-program
curl -fsS -o /dev/null -w '%{http_code}\n' https://girisimcilikvakfi.org/board-of-trustees
curl -fsS https://girisimcilikvakfi.org/api/v1/content/home | head -c 200
```

Then look at one page in a browser: images must come from `/media/…` (not from
`airtableusercontent.com` — that would mean the mirror cannot write its volume),
and the newsletter form must answer with a message rather than a network error.

Logs: `docker compose logs -f backend` — one JSON object per line, with
`request_id`. A page that fails to render logs `content_source_unavailable` with
what it served instead (`stale` or `seed`).
