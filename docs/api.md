# API

Base URL: the API process. Public paths are versioned in the path (`/v1/...`).
Browsers reach it through the reverse proxy at `/api/v1/...` (nginx strips
`/api`), so no API hostname appears in the page.

Spec: `/docs` and `/openapi.json` when `DOCS_ENABLED=true` — off in production.
There is no hand-maintained spec file; FastAPI generates it from the schemas.

Data shapes: [data-model.md](data-model.md). Architecture: [architecture/overview.md](architecture/overview.md).

## Endpoints

| Method | Path | For |
|---|---|---|
| `GET` | `/health` | liveness. Touches no database, no cache |
| `GET` | `/v1/content/home` | home page payload |
| `GET` | `/v1/content/about` | about page payload |
| `GET` | `/v1/content/fellow` | fellow-program page payload |
| `GET` | `/v1/content/people` | trustees, directors, team, fellows, alumni, challengers |
| `GET` | `/v1/content/ventures` | one page of one tab of the founders & ventures directory |
| `POST` | `/v1/newsletter` | subscribe one email address |
| `POST` | `/v1/content/refresh` | operator: drop the content snapshot |
| `GET` | `/media/<file>` | mirrored Airtable attachment, immutable |

## Content responses

The payload is the page. There is no envelope — no `data`, no `success`.

Every content response carries:

- `ETag` — send it back as `If-None-Match` and an unchanged page costs a `304`
- `Cache-Control: public, max-age=…, stale-while-revalidate=…` — values from
  `CONTENT__HTTP_MAX_AGE_SECONDS` and `CONTENT__HTTP_STALE_WHILE_REVALIDATE_SECONDS`
- `X-Request-ID` — echoed on every response, 2xx and error alike

```
GET /v1/content/home
200
{
  "seo": { "title": "GİRVAK — …", "description": "…" },
  "hero": { "base_text": "…", "rotator_words": ["…"], "images": ["/media/attX_full.jpg"], "ctas": [ … ] },
  "impact": [ { "count": 1.3, "decimals": 1, "suffix": "M+", "label": "applications", "row": 1, "col": 1, … } ],
  "what_we_do": [ … ], "fellows": [ … ], "partners": { … }, "footer": { … }
}
```

An Airtable outage does not fail the request: the API serves its last good
snapshot, and the committed seed if it never had one.

## Ventures

The one content path that takes a query. Everything else returns a whole page;
this returns **one page of one list**.

The page has two tabs over two different tables, so `kind` picks which list
`page` walks — ~180 founders against ~33 ventures, and one page number spanning
both would mean nothing.

```
GET /v1/content/ventures?kind=founders&page=2&per_page=12&sector=ai&program=zemin360&year=26&q=ayse
```

| Parameter | Default | Meaning |
|---|---|---|
| `kind` | `ventures` | `ventures` fills `items`, `founders` fills `founders`. The other list is empty |
| `page` | `1` | 1-based. Past the end **clamps to the last page** — it is not a 404 |
| `per_page` | `12` | capped at `48`; a larger value is silently reduced |
| `sector` | — | sector slug, repeat to widen (`ai` OR `ed-tech`) |
| `program` | — | programme slug, repeat to widen |
| `year` | — | cohort key, digits only (`26`), repeat to widen |
| `q` | — | free text over the card's own words |

`sector` and `program` narrow each other (AND); repeated values inside one of
them widen (OR). Slugs are ASCII-folded, so `ag-tech / food-tech` is
`ag-tech-food-tech` and a shared link stays readable.

```
200
{
  "seo": { … }, "headline": "those who create impact.", "intro": "…",
  "kind": "ventures",
  "items": [ { "slug": "algofact", "name": "ALGOFACT", "description": "is a consultancy …",
               "website": "https://algofact.tech", "logo": "/media/attX_orig.png", "year": "’25",
               "sectors": ["ai"], "sector_slugs": ["ai"],
               "programs": ["Zemin360"], "program_slugs": ["zemin360"],
               "founders": [ { "name": "…", "year": "’25", "photo": "/media/…", "linkedin": "…" } ] } ],
  "founders": [],
  "page": { "page": 2, "per_page": 12, "total": 33, "total_pages": 3,
            "has_prev": true, "has_next": true },
  "sectors": [ { "value": "ai", "label": "ai", "count": 14 } ],
  "programs": [ { "value": "zemin360", "label": "Zemin360", "count": 23 } ],
  "years": [ { "value": "26", "label": "’26", "count": 39 } ],
  "selected": { "sectors": ["ai"], "programs": [], "years": [], "q": "" }
}
```

With `kind=founders`, `founders` carries the page instead:

```
{ "slug": "ahmet-uysal", "name": "Ahmet Uysal", "year": "’26", "photo": "", "linkedin": "",
  "venture": "Teachfluence", "venture_slug": "teachfluence",
  "sectors": ["ed-tech"], "sector_slugs": ["ed-tech"],
  "programs": ["TSKB Co-venture"], "program_slugs": ["tskb-co-venture"] }
```

**Facets always describe both tabs**, so a dropdown offers the same choices
whichever tab is open — a programme only founders carry is still listed. Each
dimension is counted against the others, so picking a programme narrows the
sector counts while leaving every sector visible to switch to.

Filtering and paging read the snapshot, never Airtable: the whole directory is
mapped once per TTL, so page 3 costs the same as page 1. The `ETag` therefore
varies by query string, and an unchanged filter still costs a `304`.

## Newsletter

```
POST /v1/newsletter
{ "email": "abone@example.com" }

201 { "message": "Teşekkürler! Bültene kaydınız alındı." }
```

Rate-limited per client address (`LIMITS__NEWSLETTER_PER_IP_PER_HOUR`).

## Refresh

```
POST /v1/content/refresh
X-Admin-Token: <ADMIN_API_KEY>

202 { "status": "refreshed" }
```

Clears the snapshot so the next request re-reads Airtable. Writes nothing —
neither to Airtable nor to the database. Rate-limited
(`LIMITS__REFRESH_PER_MINUTE`), and `401` without a valid token.

Each API process holds its own snapshot, so with more than one replica the call
must reach each of them (or the TTL will do it).

## Errors

Every 4xx and 5xx has the same three keys. Clients branch on `error_code`; the
`message` is user-facing Turkish copy.

```
{ "error_code": "NEWSLETTER_ALREADY_SUBSCRIBED", "message": "Bu e-posta adresi bültene zaten kayıtlı.", "details": {} }
```

| Status | `error_code` | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | refresh called without a valid admin token |
| 404 | `NOT_FOUND` | no such path |
| 409 | `NEWSLETTER_ALREADY_SUBSCRIBED` | that address is already on the list |
| 422 | `VALIDATION_ERROR` | schema rejected the body; `details.fields` names the fields |
| 429 | `RATE_LIMIT_EXCEEDED` | over a cap; `Retry-After` says how long to wait |
| 503 | `SERVICE_UNAVAILABLE` | a dependency is down and there was nothing cached |
| 500 | `INTERNAL_ERROR` | unhandled; the message is generic and the stack stays in the log |

## Versioning

`/v1` is the current major. Adding a field or an endpoint is not a break. A break
means `/v2` alongside `/v1`, then `Deprecation` and `Sunset` headers on `/v1`,
then `410 API_VERSION_SUNSET` — never a same-day removal.
