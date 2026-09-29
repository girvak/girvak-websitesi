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

Tables: `home`, `about`, `fellow`, `partner`, `people`, `icons` — plus the
record tables `ventures`, `sectors` and `programs_detailed` (below).

`ContentFragment` (one Airtable row):

| Field | Meaning |
|---|---|
| `name` | the fragment key (`index_hero_title`, `about_mission_text`, …). Stable; the mapping is keyed on it |
| text | the visible copy |
| hover text | secondary copy where a design element has two states |
| attachments | images / logos / icons for that fragment |
| tags | on `people`: `mh`, `yk`, `team`, `fellow`, `alumni`, `challlenger`, `founder` — decides which page a person appears on |
| `dynamic` | checkbox the backend can tick so editors see which rows the live site actually reads |

MUST NOT: a fragment `name` renamed in Airtable without the matching mapping
change in `modules/content/` — the page silently falls back to its seed value.

Field lookups are case-insensitive with aliases, because editors rename columns.

### `ventures` — a record table, not a fragment store

The exception to everything above. A row here is **a company**, not a labelled
piece of copy, and it links out to three other tables:

| Field | Meaning |
|---|---|
| `name` | the venture |
| `logo (renkli)` / `logo (beyaz)` | colour and white logo. Mirrored at original size, so alpha survives |
| `description (en)` / `description (tr)` | the blurb. Written as a predicate — *"is a consultancy…"* — so it renders after the name, never alone |
| `websitesi` | often a bare host (`yummate.co`); the mapping adds the scheme |
| `sectors` | link to `sectors` — the first filter facet |
| `program` | lookup of `programs_detailed` — the second filter facet |
| `people` | link to `people` — the founders shown on the card |
| `onay` | the publish gate. An unticked row is a draft and never renders |

Links arrive as Airtable record ids, so `modules/content/ventures.py` reads
`AirtableRecord` directly rather than through `Fragments`, which keeps only
fields. Ids are resolved to labels and slugs during mapping: **no `rec…` id ever
reaches the browser.**

### Founders are people, not venture links

The founders tab is `people` rows tagged **`founder`** and ticked **`onay`** —
the tag is the same mechanism as `mh`, `yk`, `fellow` and `alumni`, and `onay`
is the publish gate this one group is held to. The venture link is extra
information (which company they built), never what decides who is a founder.

MUST NOT: building the founders list from `ventures.people`. Only ~33 of ~180
founders have a published venture, so the link would hide the great majority of
them. A founder's programme likewise comes from `people.program`, which every
founder row carries, and not from their venture, which most do not have.

The company printed under a founder's name comes from their own
**`people.ventures`** link, resolved against the published ventures; the card
links to that venture's `websitesi`. A founder with no published venture falls
back to the free-text **`people.organisation`** for the name and gets no link.

`people.ventures` and `ventures.people` are the two sides of one Airtable link
and agree row for row; the founders tab reads the person's side, because that is
the side it is about.

MUST NOT: mirroring every `people` photo for this page. Only the founder-tagged
rows plus anyone an approved venture credits are fetched — a couple of hundred
out of a table in the thousands.

There is **no seed list of ventures or founders**. A source outage with no
snapshot shows the page's empty state rather than a stale directory of real
people and companies.

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
- `VenturesContent` — one page of one tab of the founders & ventures directory,
  plus facets covering both. Both whole lists are the snapshot; the tab, filter
  and page number are applied to it per request, so a page-3 visit reads
  Airtable exactly as often as a page-1 visit (never, within a TTL)

Each has a committed **seed** (the JSON that ships in the repo). A missing or
empty Airtable table keeps the seed value for that section, so the base can be
filled incrementally and a base outage never blanks the site.

---

## `MediaAsset` — mirrored attachment

Airtable attachment URLs expire within hours; a page that hands them to the
browser starts serving 403s the next day.

- Key: Airtable `attachment_id` — stable and immutable
- Stored: on disk under the media directory, filename `<attachment_id>_<size>.<ext>`.
  Portraits (the `large` rendition of a PNG or JPEG) are converted to WebP at
  quality 85 — `<attachment_id>_large.webp`, about 25 KB against 225 KB as PNG.
  Logos (`orig`) and vectors keep their own format and exact bytes. An image
  Pillow cannot read is kept as it arrived, never dropped
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
