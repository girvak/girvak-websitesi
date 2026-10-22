# Deployment

How the site is published on the VPS. DNS for `girisimcilikvakfi.org` lives in
**Cloudflare** (Proxied). Host nginx terminates origin TLS; Docker Compose runs
PostgreSQL, the API, and the Astro SSR site. One script does the rest after DNS
points here.

## Layout

| Port | Serves |
|---|---|
| **80 / 443** | host nginx (public; Cloudflare → this host) |
| 127.0.0.1:**8082** | backend API (container) |
| 127.0.0.1:**8083** | site, Astro SSR (container) |
| 127.0.0.1:**5432** | PostgreSQL (container, loopback only) |

nginx owns routing: `/` to the site, `/api/…` to the backend with the `/api`
prefix stripped, `/media/…` to the backend. **The site does not proxy anything
itself** — without nginx, `/api` and `/media` are 404.

## What you do once (Cloudflare + secrets)

### 1. DNS

In Cloudflare DNS for `girisimcilikvakfi.org`:

| Type | Name | Content | Proxy |
|---|---|---|---|
| A (or AAAA) | `@` | VPS public IP | **Proxied** (orange) |
| A / CNAME | `www` | same IP or apex | **Proxied** |

### 2. SSL/TLS mode

Cloudflare dashboard → **SSL/TLS** → encryption mode **Full (strict)**.

Do **not** use Flexible. Edge certificates (visitor ↔ Cloudflare) are automatic;
the origin still needs a certificate Cloudflare trusts (Origin CA).

### 3. Origin certificate

Create a **Cloudflare Origin CA** certificate and place it on the server.
Steps and paths: [deploy/ssl/README.md](../../deploy/ssl/README.md).

Short version — on the VPS, from the repo:

```bash
install -d -m 700 deploy/ssl
# write Origin CA PEM + key as:
#   deploy/ssl/origin.pem
#   deploy/ssl/origin.key
chmod 600 deploy/ssl/origin.key
```

### 4. Env file on the server

One file for compose, API, and site:

```bash
cp .env.example .env
# fill POSTGRES_PASSWORD, ADMIN_API_KEY, AIRTABLE__*, CONTENT__SOURCE=airtable, …
```

| Where | Required names |
|---|---|
| `.env` (repo root) | `POSTGRES_PASSWORD`, `ADMIN_API_KEY`, `AIRTABLE__API_KEY`, `AIRTABLE__BASE_ID`, `CONTENT__SOURCE=airtable` |
| compose `environment:` (overrides `.env`) | production `ENVIRONMENT`, `DATABASE__DSN` → `db`, `TRUSTED_HOSTS`, `CORS_ORIGINS`, `MEDIA__DIR_PATH`, frontend `API_BASE_URL=http://backend:8000` |

MUST NOT: a secret in `docker-compose.yml`, in this file, or under `docs/`.

Also once: import `backend/legacy-subscribers.db` into PostgreSQL if you still
have the old SQLite newsletter list (see Database below).

## Deploy (every release)

From the repo root on the VPS:

```bash
sudo ./deploy/deploy.sh
```

That script, in order:

1. Checks Docker, nginx, curl, openssl, env files, and origin cert material
2. Installs certs to `/etc/ssl/girvak/` if needed
3. Writes Cloudflare Real IP ranges to `/etc/nginx/conf.d/cloudflare-realip.conf`
4. Installs `deploy/nginx-site.conf` and reloads nginx
5. `git pull` (ff-only), `docker compose build`, `alembic upgrade head`, `up -d`
6. Waits for `:8082/health` and `:8083`, then smoke-tests local TLS and the public URL

Useful flags:

```bash
./deploy/deploy.sh --check-only    # prerequisites only, no changes
./deploy/deploy.sh --skip-pull     # do not git pull
./deploy/deploy.sh --skip-build    # reuse existing images
./deploy/deploy.sh --skip-public   # skip the public HTTPS smoke check
```

Manual equivalent (if you prefer not to use the script):

```bash
git pull
docker compose build
docker compose run --rm backend alembic upgrade head
docker compose up -d
sudo cp deploy/nginx-site.conf /etc/nginx/sites-available/girvak
sudo ln -sf /etc/nginx/sites-available/girvak /etc/nginx/sites-enabled/
# certs already at /etc/ssl/girvak/origin.{pem,key}
sudo nginx -t && sudo systemctl reload nginx
```

There is **no certbot step**. TLS paths are fixed in `deploy/nginx-site.conf`.
Re-copying the site file does not wipe certificates.

## Environments

- **local** — `uv run uvicorn …` + `npm run dev`. `CONTENT__SOURCE=seed` works
  with no Airtable access.
- **production** — three containers + host nginx on the VPS, Cloudflare in front.

There is no staging today.

## Build notes

```bash
docker compose build
```

Images are digest-pinned. The site image bakes **no** configuration:
`src/lib/env.ts` reads the environment at request time — changing a value is a
restart, not a rebuild.

## Database migration

Migrations are a **release step**, never a container entrypoint:

```bash
docker compose run --rm backend alembic upgrade head
```

(`deploy.sh` runs this for you.)

The previous site kept subscribers in SQLite at `backend/legacy-subscribers.db`
(git-ignored). Import into PostgreSQL once — `INSERT … ON CONFLICT DO NOTHING`
is enough. Only `newsletter_subscribers` lives in PostgreSQL; content is
Airtable's; `/media` is a cache.

## Content, after deploy

Editors change Airtable; the next page load shows it within
`CONTENT__TTL_SECONDS` (default 600). To publish immediately:

```bash
curl -X POST -H "X-Admin-Token: $ADMIN_API_KEY" \
  https://girisimcilikvakfi.org/api/v1/content/refresh
```

## Start-up

On API start with `CONTENT__SOURCE=airtable`, snapshots warm in the background
(`content_warmed` in the log). Health checks answer immediately. A visitor in
the first few seconds can still see an error page; the next request works.

## Rollback

```bash
git checkout <previous tag or commit>
./deploy/deploy.sh --skip-pull
```

Schema rollback is a **new revision**, not `alembic downgrade` on production.
The `backend_media` volume survives both directions.

## Release process

1. Merge to `main`, tag it.
2. On the VPS: `sudo ./deploy/deploy.sh`
3. Run the checks below.
4. Record user-visible changes in `CHANGELOG.md` when that file exists.

## CI/CD

Not wired yet. MUST NOT: a pipeline that migrates production without a human step.

## Checks after deploy

```bash
curl -fsS https://girisimcilikvakfi.org/api/health
curl -fsS -o /dev/null -w '%{http_code}\n' https://girisimcilikvakfi.org/
curl -fsS -o /dev/null -w '%{http_code}\n' https://girisimcilikvakfi.org/about
curl -fsS -o /dev/null -w '%{http_code}\n' https://girisimcilikvakfi.org/fellow-program
curl -fsS -o /dev/null -w '%{http_code}\n' https://girisimcilikvakfi.org/board-of-trustees
curl -fsS https://girisimcilikvakfi.org/api/v1/content/home | head -c 200
```

Browser: images from `/media/…` (not `airtableusercontent.com`); newsletter form
returns a message, not a network error.

Logs: `docker compose logs -f backend` — JSON lines with `request_id`.

## Migrating from the pre-Cloudflare / certbot setup

Port layout is unchanged. Replace the live nginx site with
`deploy/nginx-site.conf` (includes TLS). Install Origin CA under
`/etc/ssl/girvak/`. Set Cloudflare to **Full (strict)** and Proxied DNS. Remove
any certbot renewal hooks that rewrote the old site file.

Critical proxy detail (still required): `/api/` must strip the prefix —

```nginx
location /api/ { proxy_pass http://127.0.0.1:8082/; }   # trailing slash
```

`deploy/nginx-site.conf` already does this.

## Portraits as WebP (one-time notes)

Mirrored portraits are converted to WebP by the backend on first content after
ship. Old `*_large.png` files can be deleted from the media volume after a day:

```bash
find <media dir> -name '*_large.png' -delete
```

Only `*_large.png` — logos are `*_orig.png` and stay.
