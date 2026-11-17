# Architecture rules (whole repo)

These rules are taken from the code as it stands. When code and rule disagree, the code that already ships wins: fix the rule, don't bend the code to an imagined one.

## Boundaries

- **Airtable is read-only.** Only the backend talks to it (`infra/airtable`). The frontend never talks to Airtable or a database.
- **FastAPI owns every write.** There are exactly two write paths: `POST /v1/newsletter` (one row) and `POST /v1/content/refresh` (admin key, drops the cache). A third one needs a stated reason.
- **Every response is identical for every visitor.** That is what makes the HTML and JSON caching safe. Anything visitor-specific (accounts, personalisation) breaks this and is a new design, not a feature add-on.
- **Content is data.** A copy or image change must not require editing code. New editable text gets a field on a backend page model, a value in that page's seed JSON, and a mapping from Airtable.
- **Adapt to Airtable, never migrate it.** Field names are matched case-insensitively with aliases (`fragments.field`). Editors' typos stay accepted (e.g. the tag `challlenger`).
- **Config lives in one place.** Every limit, TTL, timeout and secret name is a field on `Settings` (`backend/src/girvak/config/settings.py`) and in the root `.env.example`. The frontend reads env only through `src/lib/env.ts`. Don't put literals in the code instead.

## Caching

- The backend snapshot is per page. Once a page has been built, no visitor waits on Airtable: it is warmed at startup, and an expired copy is served while one background rebuild runs. Keep that property when you add a page or table.
- Every cache layer must expire and must be clearable. No cache may outlive its TTL with no way to drop it.
- Pages that shuffle on each request send `Cache-Control: no-store`, so the API payload (and its ETag) stays stable.

## Adding things

- **A new page:**
  1. Backend: a page module, a schema, a seed JSON file, a route in `modules/content/router.py`, and a call in `service.py`.
  2. Frontend: a getter in `lib/api.ts`, types in `lib/types.ts`, and the page.
- **No new infrastructure** (Redis, queue, worker, object storage, analytics) without a written reason in `docs/architecture/overview.md`. Background work that must survive a crash would go in a new `workers/`; nothing needs that yet.
- **Docs follow the code.** When behaviour described in `docs/` changes, update that doc in the same change.

## File headers

Every source file, Python and TS/JS alike, starts with a header that says what it is:

```
Module: <path>
Layer: Router | Service | Repository | Infra | Shared | Config | Test | Lib | Page | Layout | Script
Purpose: what this file is for, and what it deliberately does not do
Dependencies: …
Called by: …
Calls: …
```

Keep `Called by` / `Calls` accurate when you move responsibilities. The Purpose often says what the file does *not* do; that is intentional.

## Language

- Code, comments, docs and logs are in English.
- Visitor-facing messages from the API are in Turkish (e.g. `"Bu e-posta adresi bültene zaten kayıtlı."`).
- Page copy comes from content: the site is English (`lang="en"`), while brand names keep Turkish letters (GİRVAK).
