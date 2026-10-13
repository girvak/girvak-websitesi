"""
Module: girvak/modules/content/programs.py
Layer: Service
Purpose: Map the /programs page: the three category tiles and, under each, its
         programs with what the filter bar reads.

         Two record tables, linked:
         - **`programs`** is the categories — Entrepreneurship Support,
           Development, Talent — each with a description and a photo.
         - **`programs_detailed`** is the programs. A row links to its category
           (`programs`), to `sectors`, and carries `target group` and `stage`
           (multi-selects), `current/past`, `discover more` (the program's own
           site) and `onay`, the publish gate: an unticked row is a draft.

         A program with no category is not on this page (the Fellow and
         Challenger rows, which have their own pages). Within a category,
         current programs come first, then past ones, each in Airtable order.

Dependencies: none
Called by: modules/content/service.py
Calls: modules/content/{fragments,schemas,ventures}.py
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from girvak.infra.airtable.client import AirtableRecord
from girvak.infra.storage.media_mirror import AttachmentRef
from girvak.modules.content.fragments import (
    FULL,
    LARGE,
    Fields,
    Fragments,
    collect_refs,
    field,
    labels,
    linked_ids,
    linked_labels,
    safe_href,
    text,
)
from girvak.modules.content.schemas import ProgramCard, ProgramCategory, ProgramsContent
from girvak.modules.content.ventures import slugify

_APPROVED_FIELDS = ("onay", "approved", "active")
_CATEGORY_NAME_FIELDS = ("name", "name (en)")
_CATEGORY_TEXT_FIELDS = ("description", "text")
_PROGRAM_NAME_FIELDS = ("name (en)", "name", "name (tr)")
_PROGRAM_TEXT_FIELDS = ("text", "description")
_CATEGORY_LINK_FIELDS = ("programs", "program", "category")
_SECTOR_LINK_FIELDS = ("sectors", "sector")
_SECTOR_NAME_FIELDS = ("sectors", "sector", "name")
_TARGET_FIELDS = ("target group", "target", "target groups")
_STAGE_FIELDS = ("stage", "stages")
_STATUS_FIELDS = ("current/past", "status")
_LINK_FIELDS = ("discover more", "website", "link")
_PHOTO_FIELDS = ("photo", "image", "attachments")

# The design's order of the three tiles. The API hands rows back in creation
# order, which is not the order the page is drawn in; a category not named here
# (a fourth one, added later) follows these, in Airtable order.
_TILE_ORDER = ("entrepreneurship", "development", "talent")


def build(
    categories: Sequence[AirtableRecord],
    programs: Sequence[AirtableRecord],
    sectors: Sequence[AirtableRecord],
    media: Mapping[str, str],
) -> ProgramsContent:
    """Every category with its approved programs.

    Args:
        categories: Rows of the `programs` table.
        programs: Rows of `programs_detailed`.
        sectors: Rows of `sectors`, for the sector labels.
        media: Mirrored attachment URLs, keyed as the mirror keys them.

    Returns:
        The tiles in the design's order, each with its programs.
    """
    images = Fragments([], media)
    sector_labels = labels(sectors, _SECTOR_NAME_FIELDS)

    by_category: dict[str, list[ProgramCard]] = {record.id: [] for record in categories}
    used: set[str] = set()
    for record in programs:
        fields = record.fields
        name = text(field(fields, *_PROGRAM_NAME_FIELDS))
        if not name or field(fields, *_APPROVED_FIELDS) is not True:
            continue
        card = ProgramCard(
            slug=_unique(slugify(name), used),
            name=name,
            text=text(field(fields, *_PROGRAM_TEXT_FIELDS)),
            photo=images.image(fields, LARGE, *_PHOTO_FIELDS),
            href=safe_href(text(field(fields, *_LINK_FIELDS)), ""),
            sectors=linked_labels(fields, _SECTOR_LINK_FIELDS, sector_labels),
            targets=_choices(fields, _TARGET_FIELDS),
            stages=_choices(fields, _STAGE_FIELDS),
            current=text(field(fields, *_STATUS_FIELDS)).lower() != "past",
        )
        for category_id in linked_ids(fields, _CATEGORY_LINK_FIELDS):
            if category_id in by_category:
                by_category[category_id].append(card)

    tiles: list[ProgramCategory] = []
    for record in categories:
        name = text(field(record.fields, *_CATEGORY_NAME_FIELDS))
        if not name:
            continue
        cards = by_category[record.id]
        tiles.append(
            ProgramCategory(
                slug=slugify(name),
                name=name,
                description=text(field(record.fields, *_CATEGORY_TEXT_FIELDS)),
                photo=images.image(record.fields, FULL, *_PHOTO_FIELDS),
                # Current first; the sort is stable, so Airtable order holds within each.
                programs=sorted(cards, key=lambda card: not card.current),
            )
        )
    return ProgramsContent(categories=sorted(tiles, key=_tile_rank))


def media_refs(
    categories: Sequence[AirtableRecord], programs: Sequence[AirtableRecord]
) -> list[AttachmentRef]:
    """The photos this page shows: tiles at full size, program cards at `large`.

    Args:
        categories: Rows of the `programs` table.
        programs: Rows of `programs_detailed`; drafts are skipped.

    Returns:
        Attachment references for the mirror.
    """
    approved = [r for r in programs if field(r.fields, *_APPROVED_FIELDS) is True]
    return collect_refs(categories, FULL, *_PHOTO_FIELDS) + collect_refs(
        approved, LARGE, *_PHOTO_FIELDS
    )


def _choices(fields: Fields, names: Sequence[str]) -> list[str]:
    """A multi-select's values; a single select or text arrives as one value."""
    value = field(fields, *names)
    if isinstance(value, list):
        return [text(item) for item in value if text(item)]
    return [text(value)] if text(value) else []


def _tile_rank(category: ProgramCategory) -> int:
    for rank, prefix in enumerate(_TILE_ORDER):
        if category.slug.startswith(prefix):
            return rank
    return len(_TILE_ORDER)


def _unique(slug: str, used: set[str]) -> str:
    candidate, n = slug or "program", 2
    while candidate in used:
        candidate = f"{slug}-{n}"
        n += 1
    used.add(candidate)
    return candidate
