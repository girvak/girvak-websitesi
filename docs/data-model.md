# Data model

The product has **one** table of its own. Everything a visitor reads comes from
Airtable and is never written by this system.

Related: [architecture/overview.md](architecture/overview.md).

---

## Ownership at a glance

| Noun | Source of truth | Written by |
|---|---|---|
| `ContentFragment` | Airtable base (6 tables) | content editors, in Airtable |
| `MediaAsset` | disk mirror of an Airtable attachment | backend, on first read |
| page content (`HomeContent`, …) | derived from fragments at request time | nobody — computed |
| `NewsletterSubscriber` | PostgreSQL | the public newsletter form |

There is no user account, no role, and no per-visitor row. Every content
response is identical for every visitor, which is why the HTML and the JSON may
be cached (`overview.md`, *Caching*).

---

## Airtable (read-only source)

The base is a **fragment store**, not a normalised schema: one row is one
labelled piece of content. The backend maps fragments onto typed page models.
The base's shape is fixed by what editors already use — this system adapts to
it, it does not migrate it.

Tables: `home`, `about`, `fellow`, `partner`, `people`, `icons`.

`ContentFragment` (one Airtable row):

| Field | Meaning |
|---|---|
| `name` | the fragment key (`index_hero_title`, `about_mission_text`, …). Stable; the mapping is keyed on it |
| text | the visible copy |
| hover text | secondary copy where a design element has two states |
| attachments | images / logos / icons for that fragment |
| tags | on `people`: `trustee`, `director`, `fellow` — decides which page a person appears on |
| `dynamic` | checkbox the backend can tick so editors see which rows the live site actually reads |

MUST NOT: a fragment `name` renamed in Airtable without the matching mapping
change in `modules/content/` — the page silently falls back to its seed value.

Field lookups are case-insensitive with aliases, because editors rename columns.

---

## Page content (derived, not stored)

Computed per request from fragments, cached as a snapshot (`overview.md`).
These are Pydantic models, not tables.

- `HomeContent` — SEO, hero (rotating words, images), impact tiles, "what we do"
  cards, fellow spotlight, partners, footer
- `AboutContent` — mission, strip, section heads, CTA band
- `FellowContent` — CTA, "how it works" blocks, expectation cards, "what you do" items
- `PeopleContent` — people grouped by tag: trustees, directors, fellows
- `Partners` — logos, ordered, featured flag

Each has a committed **seed** (the JSON that ships in the repo). A missing or
empty Airtable table keeps the seed value for that section, so the base can be
filled incrementally and a base outage never blanks the site.

---

## `MediaAsset` — mirrored attachment

Airtable attachment URLs expire within hours; a page that hands them to the
browser starts serving 403s the next day.

- Key: Airtable `attachment_id` — stable and immutable
- Stored: on disk under the media directory, filename `<attachment_id>_<size>.<ext>`
- Served: `/media/<filename>`, immutable cache headers
- Written: once, on first read of a fragment that carries the attachment

MUST NOT: a database column holding image bytes. MUST NOT: the expiring Airtable
URL in a response the browser will keep.

---

## `NewsletterSubscriber` — the only table we own

PostgreSQL. Written by `POST /v1/newsletter`.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | `gen_random_uuid()`; never exposed to the client |
| `email` | `text` | unique (case-folded); the duplicate is a `409`, not a second row |
| `created_at` | `timestamptz` | UTC |
| `updated_at` | `timestamptz` | UTC |

Personal data: the email address, and nothing else. Retention and erasure are
`docs/security.md` once that file's trigger fires.

MUST NOT: a `name`, `source`, or `consent_text` column before the form collects it.
