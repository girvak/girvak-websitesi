# Architecture overview

GİRVAK's public website. Content lives in Airtable; the site shows it without a
rebuild. Rules the code follows: `coding-playbook/`.

Related: [../data-model.md](../data-model.md).

---

## System overview

```
Airtable (6 fragment tables)
   │   REST, Personal Access Token, read-only
   ▼
FastAPI  ── content snapshot cache (TTL from config)
         ── POST /v1/content/refresh (admin key) → clears the snapshot now
         ── /media: attachment mirror on disk (Airtable URLs expire)
         ── PostgreSQL: newsletter subscribers (the only table we write)
   │   GET /v1/content/{home,about,fellow,people}  · ETag + 304
   ▼
Astro (SSR, Node) ── renders HTML per request from the API, short-TTL page cache
   ▼
nginx :80  →  frontend :8083 · backend :8082 · /media
```

Editing Airtable and reloading the page is enough. No build step, no deploy, no
cache purge by hand.

## Actors and isolation

- **Visitor** — anonymous, reads pages, may submit the newsletter form. No account.
- **Content editor** — works in Airtable. Not a user of this system.
- **Operator** — holds `ADMIN_API_KEY`, may call the refresh endpoint.

Single tenant. No roles. No per-visitor data. Every content response is
identical for every visitor — this is what makes HTML and JSON caching safe, and
it is the reason there is no identity layer (decision below).

## Who owns writes and authz

FastAPI owns every write. Two write paths exist:

1. `POST /v1/newsletter` — public, rate-limited, writes one row.
2. `POST /v1/content/refresh` — admin key in a header, writes nothing; drops the cache.

The frontend never writes to a database and never talks to Airtable.

## Components

| Component | Owns |
|---|---|
| `backend/src/config/` | every env value, TTL, cap, timeout, secret name |
| `backend/src/http/` | transport: request id, CORS, rate limit, error JSON, mount list |
| `backend/src/modules/content/` | fragment → page mapping, snapshot policy, what a page means |
| `backend/src/modules/newsletter/` | subscribe rule, duplicate handling |
| `backend/src/infra/airtable/` | Airtable REST client. No product sentence |
| `backend/src/infra/cache/` | in-process TTL snapshot store |
| `backend/src/infra/storage/` | attachment mirror on disk |
| `backend/src/infra/db/` | session, model, repository (subscribers) |
| `frontend/` | Astro SSR pages, layouts, styles, browser scripts |

No worker process: nothing yet must survive a crash or outlive a request. When
one does (a scheduled mirror sweep, a large export), it enters as `workers/`.

## Caching

Three layers, each with one job:

1. **Content snapshot** (backend, in process) — Airtable rows mapped to page
   models, held for `CONTENT_TTL_SECONDS`. Protects Airtable's rate limit and
   makes a page render one dict lookup.
2. **HTTP** — `ETag` + `304` on content responses; `Cache-Control` with a short
   `max-age` and `stale-while-revalidate`. `/media` is immutable.
3. **Page HTML** (frontend, in process) — rendered HTML held for a short TTL, so
   a burst of visitors costs one API call.

Invalidation: TTL expiry, or `POST /v1/content/refresh` for "publish now".
Both are safe because no response is visitor-specific.

MUST NOT: a cache layer that outlives its TTL with no way to clear it.

## External systems in use today

- **Airtable** — content source. Read-only PAT. A base outage falls back to the
  committed seed JSON; the site stays up with the last shipped copy.
- **PostgreSQL** — newsletter subscribers.
- **nginx** — TLS and the public port; routes `/`, `/api`, `/media`.

Nothing else. No Redis, no queue, no object storage, no third-party analytics.

## Technical principles this product follows

- Content is data, not code. A copy change never touches a `.astro` file.
- The visitor's browser downloads no content JSON; HTML arrives filled in.
- Airtable's shape is adapted to, never migrated.
- Every limit, TTL, and secret name is a field on `Settings`.

## Known technical limits

- Airtable rate limit (5 req/s per base) — the snapshot cache is what respects it.
- A fragment renamed in Airtable falls back to the seed silently. Editors see the
  `dynamic` checkbox to know which rows are live.
- SSR means the frontend is a running Node process, not a static bundle: it must
  be restarted on deploy and monitored.

## Decisions taken on the user's behalf

- **No identity layer.** No visitor account exists, so there is no login, no
  session, and no ownership check. The only privileged call is the refresh
  endpoint, gated by a shared admin key. Revisit when the product grows a member
  area — that is a new task with its own plan, not a feature add-on.
- **SSR instead of browser-side content fetching.** The requirement was "changes
  appear on reload, no rebuild". SSR satisfies it while keeping first paint and
  SEO intact; a browser fetch would trade both away for the same freshness.
- **Astro stays.** The design transfers one-to-one and ships almost no JS. The
  playbook's frontend rules are Next.js-specific, so an `astro-frontend` stack
  folder is added to the playbook rather than bending the Next.js rules.
- **PostgreSQL for subscribers**, replacing the previous SQLite file: one
  process writes it today, but a container filesystem is not a durable store.

## Out of scope

The `alt` and `classic` experiment pages, user accounts, an admin UI inside the
site (Airtable is the CMS), site search, a second language, and Redis.
