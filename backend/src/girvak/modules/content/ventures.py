"""
Module: girvak/modules/content/ventures.py
Layer: Service
Purpose: Map the founders & ventures page, then cut one list down to the page a
         visitor asked for.

         The page has two tabs over two different tables:
         - **founders** are `people` rows tagged `founder`, read the same way
           trustees and fellows are. Most of them have no venture on the site;
           they are founders all the same, so the venture link must not be what
           decides who appears.
         - **ventures** are rows of the `ventures` table, which links out to
           `sectors`, `programs_detailed` and `people`.

         Unlike home/about/fellow, neither is a fragment store: a row is a
         person or a company, not a labelled piece of copy, and the links arrive
         as Airtable record ids. `Fragments` keeps only fields, so this module
         reads AirtableRecord directly and builds its own indexes.

         The page's own words are not here: they come from the committed seed,
         because Airtable has no copy table for this page.

Dependencies: none
Called by: modules/content/service.py
Calls: modules/content/{fragments,people,schemas}.py
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from girvak.infra.airtable.client import AirtableRecord
from girvak.infra.storage.media_mirror import AttachmentRef, attachment_ref, cache_key
from girvak.modules.content.fragments import (
    LARGE,
    ORIGINAL,
    Fields,
    Fragments,
    field,
    safe_href,
    tags,
    text,
)
from girvak.modules.content.people import sort_key, year_of
from girvak.modules.content.schemas import (
    Facet,
    FounderCard,
    PageInfo,
    Venture,
    VentureFounder,
    VenturesContent,
    VenturesCopy,
    VenturesQuery,
)

Kind = Literal["ventures", "founders"]

# Who counts as a founder. The `people` table's own tag, alongside `mh`, `yk`,
# `fellow`, `alumni` and `challenger` — the venture link is extra information,
# never the gate. Most founders have no venture on the site.
FOUNDER_TAG = "founder"

# Editors tick `onay` ("approved") when a row may be shown; a row without it is
# a draft. It gates ventures, and it gates the founders tab too — unlike the
# other people groups, which people.py shows on their tag alone.
_APPROVED_FIELDS = ("onay", "approved", "active")

# The base names the two logo columns in Turkish: renkli = colour, beyaz = white.
_LOGO_COLOUR_FIELDS = ("logo (renkli)", "logo_renkli", "logo", "positive_logo")
_LOGO_WHITE_FIELDS = ("logo (beyaz)", "logo_beyaz", "logo_white", "negative_logo")

_DESCRIPTION_EN_FIELDS = ("description (en)", "description_en", "description")
_DESCRIPTION_TR_FIELDS = ("description (tr)", "description_tr")
_WEBSITE_FIELDS = ("websitesi", "website", "url", "link")

_SECTOR_LINK_FIELDS = ("sectors", "sector")
_PROGRAM_LINK_FIELDS = ("program", "programs")
_PEOPLE_LINK_FIELDS = ("people", "founders", "founder")
# The person's side of the same link. Airtable keeps the two sides in step, so
# either would do; reading it from the person is what the founders tab is about.
_VENTURE_LINK_FIELDS = ("ventures", "venture")
_PHOTO_FIELDS = ("photo", "attachments", "image")

# Label column of each linked table.
_SECTOR_NAME_FIELDS = ("sectors", "sector", "name")
_PROGRAM_NAME_FIELDS = ("name (en)", "name_en", "name", "name (tr)")

# How many cards one page shows, and the ceiling a caller may ask for. The cap
# exists so `?per_page=100000` cannot turn one request into the whole table.
DEFAULT_PER_PAGE = 12
MAX_PER_PAGE = 48

# A venture's own sector, when the editor typed it into `other sector` instead
# of linking one. Grouped under a single facet rather than inventing one each.
_OTHER_SECTOR_LABEL = "other"

_TURKISH_ASCII = str.maketrans(
    {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
    }
)

# A card is whatever the two tabs render. Both filter on the same four things.
_Card = Venture | FounderCard


@dataclass(frozen=True)
class VenturesData:
    """Both tabs, mapped once per TTL.

    This is what the snapshot holds. One visitor's tab, filter and page number
    are applied to it per request by `select`, so paging costs Airtable nothing.
    """

    copy: VenturesCopy
    items: tuple[Venture, ...]
    founders: tuple[FounderCard, ...]


def build(
    copy: VenturesCopy,
    ventures: Sequence[AirtableRecord],
    sectors: Sequence[AirtableRecord],
    programs: Sequence[AirtableRecord],
    people: Sequence[AirtableRecord],
    media: Mapping[str, str],
) -> VenturesData:
    """Resolve both tabs and everything they link to.

    Args:
        copy: The page's committed words.
        ventures: Rows of the Airtable `ventures` table.
        sectors: Rows of the `sectors` table, for the sector labels.
        programs: Rows of `programs_detailed`, for the programme labels.
        people: Rows of the `people` table — the founders themselves, and the
            names a venture card credits.
        media: Mirrored attachment URLs, keyed as the mirror keys them.

    Returns:
        Both lists, each sorted Turkish-alphabetically by name.
    """
    # Ventures resolve their own logos (see `_logo`); only people go through
    # Fragments, for the portrait rendition.
    people_media = Fragments(people, media)

    sector_labels = _labels(sectors, _SECTOR_NAME_FIELDS)
    program_labels = _labels(programs, _PROGRAM_NAME_FIELDS)
    people_rows = {record.id: record.fields for record in people}

    items: list[Venture] = []
    used_slugs: set[str] = set()
    # Published ventures by Airtable id, so a founder's `ventures` link resolves
    # without a second scan. Only approved ones are in here: a draft venture
    # must not reach a founder card either.
    published: dict[str, Venture] = {}

    for record in ventures:
        fields = record.fields
        if not _approved(fields):
            continue
        name = text(field(fields, "name"))
        if not name:
            continue

        labels = _linked_labels(fields, _SECTOR_LINK_FIELDS, sector_labels)
        other = text(field(fields, "other sector", "other_sector"))
        if other and not labels:
            labels = [_OTHER_SECTOR_LABEL]

        program_names = _linked_labels(fields, _PROGRAM_LINK_FIELDS, program_labels)
        credited = _venture_founders(fields, people_rows, people_media)
        # A venture has no year of its own in the base; it is shown under the
        # cohort of the founder who brought it, which is the first one linked.
        year = next((f.year for f in credited if f.year), "")

        venture = Venture(
            slug=_unique_slug(name, used_slugs),
            name=name,
            description=text(field(fields, *_DESCRIPTION_EN_FIELDS)),
            description_tr=text(field(fields, *_DESCRIPTION_TR_FIELDS)),
            website=_website(fields),
            logo=_logo(fields, media, _LOGO_COLOUR_FIELDS),
            logo_white=_logo(fields, media, _LOGO_WHITE_FIELDS),
            year=year,
            sectors=labels,
            sector_slugs=[slugify(label) for label in labels],
            programs=program_names,
            program_slugs=[slugify(label) for label in program_names],
            founders=credited,
        )
        items.append(venture)
        published[record.id] = venture

    items.sort(key=lambda venture: sort_key(venture.name))
    founders = _founder_cards(people, people_media, program_labels, published, used_slugs)
    return VenturesData(copy=copy, items=tuple(items), founders=tuple(founders))


def select(
    data: VenturesData,
    *,
    kind: Kind = "ventures",
    sectors: Sequence[str] = (),
    programs: Sequence[str] = (),
    years: Sequence[str] = (),
    q: str = "",
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> VenturesContent:
    """Cut one tab down to one page, and list what the filters offer.

    `kind` picks which list `page` walks. The two tabs are very different
    lengths — a few dozen ventures against a few hundred founders — so one page
    number spanning both would mean nothing.

    A page past the end is clamped rather than refused: narrowing a filter while
    on page 3 is an ordinary thing to do, and an empty 404 would be a worse
    answer than the last page of the new result set.

    Args:
        data: Both mapped lists.
        kind: Which tab to page through.
        sectors: Sector slugs to keep; empty means every sector.
        programs: Programme slugs to keep; empty means every programme.
        years: Cohort keys (`26`) to keep; empty means every cohort.
        q: Free text matched against the card's own words.
        page: 1-based page number.
        per_page: Cards per page, capped at MAX_PER_PAGE.

    Returns:
        One page of the chosen tab, plus facets that always describe both tabs
        so a dropdown offers the same choices whichever tab is open.
    """
    wanted_sectors = _clean(sectors)
    wanted_programs = _clean(programs)
    wanted_years = _clean(years, year_slug)
    needle = q.strip()
    # Folded once here rather than per card per pool: `Ayşe` and `ayse` must
    # find the same row, so both sides go through the same transliteration.
    folded = _fold(needle)

    def keep(cards: Sequence[_Card], skip: str = "") -> list[_Card]:
        return [
            card
            for card in cards
            if _matches(
                card,
                () if skip == "sector" else wanted_sectors,
                () if skip == "program" else wanted_programs,
                () if skip == "year" else wanted_years,
                folded,
            )
        ]

    chosen: tuple[_Card, ...] = data.founders if kind == "founders" else data.items
    matched = keep(chosen)

    size = max(1, min(per_page, MAX_PER_PAGE))
    total = len(matched)
    total_pages = max(1, math.ceil(total / size))
    current = max(1, min(page, total_pages))
    start = (current - 1) * size
    window = matched[start : start + size]

    # Facets cover both tabs: a programme only founders carry must still be
    # offered. Each dimension is counted against the others, so picking a
    # programme narrows the sector list without hiding the sector you are on.
    both: tuple[_Card, ...] = (*data.items, *data.founders)

    return VenturesContent(
        **data.copy.model_dump(),
        kind=kind,
        items=[card for card in window if isinstance(card, Venture)],
        founders=[card for card in window if isinstance(card, FounderCard)],
        page=PageInfo(
            page=current,
            per_page=size,
            total=total,
            total_pages=total_pages,
            has_prev=current > 1,
            has_next=current < total_pages,
        ),
        sectors=_facets(
            keep(both, "sector"), lambda c: zip(c.sector_slugs, c.sectors, strict=True)
        ),
        programs=_facets(
            keep(both, "program"), lambda c: zip(c.program_slugs, c.programs, strict=True)
        ),
        years=_year_facets(keep(both, "year")),
        selected=VenturesQuery(
            sectors=wanted_sectors, programs=wanted_programs, years=wanted_years, q=needle
        ),
    )


def media_refs(
    ventures: Sequence[AirtableRecord], people: Sequence[AirtableRecord]
) -> list[AttachmentRef]:
    """Attachments this page will ask for, and no others.

    Logos keep their alpha channel, so they are mirrored at their original size.
    Portraits render small, so they use the `large` rendition — and only for
    people the page shows: everyone tagged `founder`, plus anyone an approved
    venture credits. That is a couple of hundred rows out of a `people` table in
    the thousands.

    Args:
        ventures: Rows of the `ventures` table.
        people: Rows of the `people` table.

    Returns:
        One reference per attachment the mapping will resolve.
    """
    refs: list[AttachmentRef] = []
    credited: set[str] = set()

    for record in ventures:
        if not _approved(record.fields):
            continue
        for name in (*_LOGO_COLOUR_FIELDS, *_LOGO_WHITE_FIELDS):
            refs.extend(_refs_of(record.fields, name, ORIGINAL))
        credited.update(_linked_ids(record.fields, _PEOPLE_LINK_FIELDS))

    for record in people:
        shown = record.id in credited or (
            _is_founder(record.fields) and _approved(record.fields)
        )
        if shown:
            for name in _PHOTO_FIELDS:
                refs.extend(_refs_of(record.fields, name, LARGE))

    return refs


def slugify(value: str) -> str:
    """URL-safe key for a filter value.

    `ag-tech / food-tech` becomes `ag-tech-food-tech`, so a sector survives a
    query string without percent-encoding and a shared link stays readable.

    Args:
        value: The label as Airtable holds it.

    Returns:
        The slug, empty when the label has no usable characters.
    """
    folded = value.strip().translate(_TURKISH_ASCII).casefold()
    ascii_only = unicodedata.normalize("NFKD", folded).encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", ascii_only)).strip("-")


def year_slug(value: str) -> str:
    """Filter key of a cohort year: `’26` and `2026` both become `26`.

    Years carry a typographic apostrophe the design prints but a query string
    should not have to, so the digits alone are the key.

    Args:
        value: The year as the card shows it.

    Returns:
        The last two digits, empty when there are none.
    """
    digits = re.sub(r"\D", "", value or "")
    return digits[-2:] if digits else ""


def _founder_cards(
    people: Sequence[AirtableRecord],
    media: Fragments,
    program_labels: Mapping[str, str],
    published: Mapping[str, Venture],
    used_slugs: set[str],
) -> list[FounderCard]:
    """Every approved person tagged `founder`, with their venture."""
    cards: list[FounderCard] = []
    for record in people:
        fields = record.fields
        if not _is_founder(fields) or not _approved(fields):
            continue
        name = text(field(fields, "name"))
        if not name:
            continue

        # Programmes come from the person, not the venture: every founder row
        # carries them, and a founder without a venture would otherwise have
        # nothing to filter on.
        programs = _linked_labels(fields, _PROGRAM_LINK_FIELDS, program_labels)
        venture = _first_venture(fields, published)
        if venture and not programs:
            programs = list(venture.programs)

        # The company printed under the name. Their published venture is the
        # curated record and names it; `organisation` is what a founder without
        # one is left with, so it stays as the fallback.
        company = text(field(fields, "organisation", "organization", "company"))

        cards.append(
            FounderCard(
                slug=_unique_slug(name, used_slugs),
                name=name,
                year=year_of(fields),
                photo=media.image(fields, LARGE, *_PHOTO_FIELDS),
                linkedin=safe_href(_url(text(field(fields, "linkedin"))), ""),
                venture=(venture.name if venture else "") or company,
                venture_slug=venture.slug if venture else "",
                website=venture.website if venture else "",
                sectors=list(venture.sectors) if venture else [],
                sector_slugs=list(venture.sector_slugs) if venture else [],
                programs=programs,
                program_slugs=[slugify(label) for label in programs],
            )
        )

    cards.sort(key=lambda card: sort_key(card.name))
    return cards


def _first_venture(fields: Fields, published: Mapping[str, Venture]) -> Venture | None:
    """The first published venture on a person's `ventures` link.

    A founder may link several; the card shows one. Drafts are skipped rather
    than shown, so a venture an editor has not approved never reaches the page
    through the founders tab either.
    """
    for record_id in _linked_ids(fields, _VENTURE_LINK_FIELDS):
        venture = published.get(record_id)
        if venture is not None:
            return venture
    return None


def _venture_founders(
    fields: Fields, people: Mapping[str, Fields], media: Fragments
) -> list[VentureFounder]:
    """The people a venture credits, for its own card."""
    founders: list[VentureFounder] = []
    for record_id in _linked_ids(fields, _PEOPLE_LINK_FIELDS):
        row = people.get(record_id)
        if row is None:
            continue
        name = text(field(row, "name"))
        if not name:
            continue
        founders.append(
            VentureFounder(
                name=name,
                title=text(field(row, "title", "position")),
                photo=media.image(row, LARGE, *_PHOTO_FIELDS),
                linkedin=safe_href(_url(text(field(row, "linkedin"))), ""),
                year=year_of(row),
            )
        )
    return founders


def _is_founder(fields: Fields) -> bool:
    return any(str(tag).strip().lower() == FOUNDER_TAG for tag in tags(fields))


def _approved(fields: Fields) -> bool:
    return field(fields, *_APPROVED_FIELDS) is True


def _clean(values: Sequence[str], key: Callable[[str], str] = slugify) -> list[str]:
    """Keys a caller sent, normalised and de-duplicated, order kept."""
    seen: list[str] = []
    for value in values:
        slug = key(value)
        if slug and slug not in seen:
            seen.append(slug)
    return seen


def _matches(
    card: _Card,
    sectors: Sequence[str],
    programs: Sequence[str],
    years: Sequence[str],
    folded_needle: str,
) -> bool:
    """One card against the active filter.

    Several values in one dimension widen it (OR); the dimensions narrow each
    other (AND). `folded_needle` must already have been through `_fold`.
    """
    if sectors and not any(slug in sectors for slug in card.sector_slugs):
        return False
    if programs and not any(slug in programs for slug in card.program_slugs):
        return False
    if years and year_slug(card.year) not in years:
        return False
    if folded_needle and folded_needle not in _haystack(card):
        return False
    return True


def _fold(value: str) -> str:
    """Case- and diacritic-insensitive form, so `Ayşe` and `ayse` are one word."""
    return value.translate(_TURKISH_ASCII).casefold()


def _haystack(card: _Card) -> str:
    if isinstance(card, FounderCard):
        return _fold(f"{card.name} {card.venture}")
    credited = " ".join(founder.name for founder in card.founders)
    return _fold(f"{card.name} {card.description} {card.description_tr} {credited}")


def _facets(
    pool: Sequence[_Card], pairs: Callable[[_Card], Iterable[tuple[str, str]]]
) -> list[Facet]:
    """Count one dimension over a pool, ordered by count then label."""
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for card in pool:
        for slug, label in pairs(card):
            if not slug:
                continue
            counts[slug] = counts.get(slug, 0) + 1
            labels.setdefault(slug, label)
    return [
        Facet(value=slug, label=labels[slug], count=count)
        for slug, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _year_facets(pool: Sequence[_Card]) -> list[Facet]:
    """Cohort counts, newest first — the order the design's dropdown lists them."""
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for card in pool:
        key = year_slug(card.year)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
        labels.setdefault(key, card.year)
    return [
        Facet(value=key, label=labels[key], count=counts[key])
        for key in sorted(counts, reverse=True)
    ]


def _labels(records: Sequence[AirtableRecord], names: Sequence[str]) -> dict[str, str]:
    """Record id -> that row's label, for a linked table."""
    resolved: dict[str, str] = {}
    for record in records:
        label = text(field(record.fields, *names))
        if label:
            resolved[record.id] = label
    return resolved


def _linked_ids(fields: Fields, names: Sequence[str]) -> list[str]:
    """Record ids of a link or lookup column.

    A lookup gives plain id strings and a link column gives the same, but a
    lookup configured to return objects gives dicts — both are read here so a
    change in the base does not empty the column.
    """
    value = field(fields, *names)
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        if isinstance(item, str) and item.startswith("rec"):
            ids.append(item)
        elif isinstance(item, dict):
            candidate = item.get("id")
            if isinstance(candidate, str) and candidate.startswith("rec"):
                ids.append(candidate)
    return ids


def _linked_labels(fields: Fields, names: Sequence[str], labels: Mapping[str, str]) -> list[str]:
    """Labels of a link column, duplicates dropped and order kept."""
    resolved: list[str] = []
    for record_id in _linked_ids(fields, names):
        label = labels.get(record_id)
        if label and label not in resolved:
            resolved.append(label)
    return resolved


def _logo(fields: Fields, media: Mapping[str, str], names: Sequence[str]) -> str:
    """First logo attachment a browser can actually paint.

    Editors drop whatever the agency sent into these columns, so one venture's
    "logo" is a PDF. An `<img>` pointed at that renders nothing, and the card
    would show an empty square — so anything that is not an image is skipped and
    the other column gets its turn.

    Args:
        fields: One venture row's fields.
        media: Mirrored attachment URLs.
        names: Column aliases to try, in order.

    Returns:
        The mirrored URL, the expiring Airtable URL when the mirror has no copy
        yet, or an empty string when the row has no usable logo.
    """
    value = field(fields, *names)
    if not isinstance(value, list):
        return ""
    for attachment in value:
        if not isinstance(attachment, dict):
            continue
        if not str(attachment.get("type") or "").lower().startswith("image/"):
            continue
        ref = attachment_ref(attachment, ORIGINAL)
        if ref is None:
            continue
        url = media.get(cache_key(ref.attachment_id, ref.requested), ref.remote_url)
        if url:
            return url
    return ""


def _website(fields: Fields) -> str:
    """The venture's site as a usable href.

    Editors type `yummate.co` as often as `https://algofact.tech`, and a bare
    host in an href resolves against this site instead of leaving it.
    """
    return safe_href(_url(text(field(fields, *_WEBSITE_FIELDS))), "")


def _url(value: str) -> str:
    if not value:
        return ""
    if re.match(r"^[a-z][a-z0-9+.-]*:", value, re.I):
        return value
    return f"https://{value.lstrip('/')}"


def _unique_slug(name: str, used: set[str]) -> str:
    """A stable, unique key. Four founders share a name in the base, and two
    rows with the same slug would collide in a URL."""
    base = slugify(name) or "entry"
    slug = base
    suffix = 2
    while slug in used:
        slug = f"{base}-{suffix}"
        suffix += 1
    used.add(slug)
    return slug


def _refs_of(fields: Fields, name: str, variant: str) -> Iterable[AttachmentRef]:
    """Image attachments of one column. Anything else — a PDF dropped in a logo
    column — is skipped here too, so the mirror never fetches what no `<img>`
    could paint."""
    value = field(fields, name)
    if not isinstance(value, list):
        return []
    refs: list[AttachmentRef] = []
    for attachment in value:
        if not isinstance(attachment, dict):
            continue
        if not str(attachment.get("type") or "").lower().startswith("image/"):
            continue
        ref = attachment_ref(attachment, variant)
        if ref is not None:
            refs.append(ref)
    return refs
