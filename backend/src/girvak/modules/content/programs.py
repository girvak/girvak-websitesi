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

         The same rows make each program's own page (`/programs/<slug>`):
         - `text` is the short line on the program's card here;
         - `program overview` is the description over the page's photo, one
           paragraph per line, `**x**` highlights;
         - `data1`…`data4` are the four counted boxes: the first line is the
           figure and its words ("27 ventures", "12–85 age range", "Since 2016"),
           the rest is the sentence that opens on hover;
         - `for who` and `what happens` are lists, one item per line;
         - `partner` links the `partner` table (several allowed).
         Where the row has nothing the committed copy in
         `data/program_details.json` answers; where that has nothing either the
         block is left out, not made up ("for who" falls back to the row's own
         target group, stage and sectors).

         A program with no category is not on this page (the Fellow and
         Challenger rows, which have their own pages). Within a category,
         current programs come first, then past ones, each in Airtable order.

Dependencies: none
Called by: modules/content/service.py
Calls: modules/content/{fragments,schemas,ventures}.py
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from girvak.infra.airtable.client import AirtableRecord
from girvak.infra.storage.media_mirror import AttachmentRef
from girvak.modules.content import seeds
from girvak.modules.content.fragments import (
    FULL,
    LARGE,
    Fields,
    Fragments,
    collect_refs,
    field,
    labels,
    link_of,
    linked_ids,
    linked_labels,
    logo_refs,
    safe_href,
    text,
)
from girvak.modules.content.markup import highlight
from girvak.modules.content.schemas import (
    Partner,
    ProgramCard,
    ProgramCategory,
    ProgramsContent,
    ProgramStat,
)
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
_OVERVIEW_FIELDS = ("program overview", "overview")
_FOR_WHO_FIELDS = ("for who", "for_who")
_WHAT_HAPPENS_FIELDS = ("what happens", "what_happens")
_PARTNER_LINK_FIELDS = ("partner", "partners")
_PARTNER_NAME_FIELDS = ("organization", "organisation", "name")
_STAT_COUNT = 4

# The design's order of the three tiles. The API hands rows back in creation
# order, which is not the order the page is drawn in; a category not named here
# (a fourth one, added later) follows these, in Airtable order.
_TILE_ORDER = ("entrepreneurship", "development", "talent")


def build(
    categories: Sequence[AirtableRecord],
    programs: Sequence[AirtableRecord],
    sectors: Sequence[AirtableRecord],
    media: Mapping[str, str],
    partners: Sequence[AirtableRecord] = (),
) -> ProgramsContent:
    """Every category with its approved programs.

    Args:
        categories: Rows of the `programs` table.
        programs: Rows of `programs_detailed`.
        sectors: Rows of `sectors`, for the sector labels.
        media: Mirrored attachment URLs, keyed as the mirror keys them.
        partners: Rows of the `partner` table, for the organisations a program links to.

    Returns:
        The tiles in the design's order, each with its programs.
    """
    images = Fragments([], media)
    sector_labels = labels(sectors, _SECTOR_NAME_FIELDS)
    partner_rows = Fragments(partners, media)
    partner_by_id = {
        record.id: Partner(
            name=text(field(record.fields, *_PARTNER_NAME_FIELDS)),
            logo=partner_rows.logo(record.fields),
            href=link_of(record.fields, ""),
        )
        for record in partners
        if text(field(record.fields, *_PARTNER_NAME_FIELDS))
    }

    by_category: dict[str, list[ProgramCard]] = {record.id: [] for record in categories}
    used: set[str] = set()
    for record in programs:
        fields = record.fields
        name = text(field(fields, *_PROGRAM_NAME_FIELDS))
        if not name or field(fields, *_APPROVED_FIELDS) is not True:
            continue
        slug = _unique(slugify(name), used)
        sector_names = linked_labels(fields, _SECTOR_LINK_FIELDS, sector_labels)
        targets = _choices(fields, _TARGET_FIELDS)
        stages = _choices(fields, _STAGE_FIELDS)
        committed = seeds.program_details().get(slug)
        card = ProgramCard(
            slug=slug,
            name=name,
            text=text(field(fields, *_PROGRAM_TEXT_FIELDS)),
            photo=images.image(fields, LARGE, *_PHOTO_FIELDS),
            hero=images.image(fields, FULL, *_PHOTO_FIELDS),
            href=safe_href(text(field(fields, *_LINK_FIELDS)), ""),
            sectors=sector_names,
            targets=targets,
            stages=stages,
            current=text(field(fields, *_STATUS_FIELDS)).lower() != "past",
            body_html=[highlight(line) for line in _lines(field(fields, *_OVERVIEW_FIELDS))]
            or [highlight(line) for line in (committed.body if committed else [])],
            stats=_stats(fields) or (list(committed.stats) if committed else []),
            for_who=_lines(field(fields, *_FOR_WHO_FIELDS))
            or (list(committed.for_who) if committed and committed.for_who else [])
            or _derived_for_who(targets, stages, sector_names),
            what_happens=_lines(field(fields, *_WHAT_HAPPENS_FIELDS))
            or (list(committed.what_happens) if committed else []),
            partners=_partners_of(fields, partner_by_id, committed.partner if committed else ""),
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
    categories: Sequence[AirtableRecord],
    programs: Sequence[AirtableRecord],
    partners: Sequence[AirtableRecord] = (),
) -> list[AttachmentRef]:
    """The photos this page shows: tiles at full size, program cards at `large`.

    Args:
        categories: Rows of the `programs` table.
        programs: Rows of `programs_detailed`; drafts are skipped.
        partners: Rows of the `partner` table, for the logos on a program's page.

    Returns:
        Attachment references for the mirror.
    """
    approved = [r for r in programs if field(r.fields, *_APPROVED_FIELDS) is True]
    # Cards use the small variant; a program's own page opens with the full one.
    return (
        collect_refs(categories, FULL, *_PHOTO_FIELDS)
        + collect_refs(approved, LARGE, *_PHOTO_FIELDS)
        + collect_refs(approved, FULL, *_PHOTO_FIELDS)
        + logo_refs(partners)
    )


def _partners_of(
    fields: Fields, known: Mapping[str, Partner], committed_name: str
) -> list[Partner]:
    """The organisations a program links to; failing that, the committed name looked up.

    A linked row that is not in the partner table (a draft, a deleted row) is
    skipped. The committed copy names one partner, matched by name.
    """
    found = [known[i] for i in linked_ids(fields, _PARTNER_LINK_FIELDS) if i in known]
    if found or not committed_name:
        return found
    wanted = committed_name.casefold()
    return [p for p in known.values() if wanted in p.name.casefold()][:1]


def _lines(value: object) -> list[str]:
    """One item per non-empty line, a leading bullet mark dropped."""
    return [
        line.lstrip("•-– ").strip()
        for line in text(value).splitlines()
        if line.lstrip("•-– ").strip()
    ]


_DATA_BOX = re.compile(r"^(?P<prefix>\D*?)(?P<number>\d[\d,]*(?:\.\d+)?)(?P<rest>.*)$")


def parse_data_box(value: str) -> ProgramStat | None:
    """One `dataN` cell: the figure and its words on the first line, a sentence after.

    `"27 ventures\\nteams supported from idea to scale."` is 27, "ventures" and the
    sentence. The figure may carry words before it ("Since 2016"), a sign right
    after it ("100%", "50+", "12–85"), and thousands separators ("1,076"), all
    kept as written. A cell with no figure in it is not a box.

    Args:
        value: The Airtable cell.

    Returns:
        The box, or None when the first line holds no number.
    """
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return None
    match = _DATA_BOX.match(lines[0])
    if match is None:
        return None
    number = match.group("number")
    rest = match.group("rest")
    suffix = rest.split(None, 1)[0] if rest and not rest[0].isspace() else ""
    label = rest[len(suffix) :].strip()
    try:
        count = float(number.replace(",", ""))
    except ValueError:
        return None
    return ProgramStat(
        value=count,
        decimals=len(number.split(".")[1]) if "." in number else 0,
        grouped="," in number,
        prefix=match.group("prefix"),
        suffix=suffix,
        label=label,
        text=" ".join(lines[1:]),
    )


def _stats(fields: Fields) -> list[ProgramStat]:
    """`data1`…`data4`, in order; a box that is empty or has no figure is skipped."""
    boxes = (
        parse_data_box(text(field(fields, f"data{n}", f"data {n}", f"data_{n}")))
        for n in range(1, _STAT_COUNT + 1)
    )
    return [box for box in boxes if box is not None]


def _derived_for_who(
    targets: Sequence[str], stages: Sequence[str], sectors: Sequence[str]
) -> list[str]:
    """What the row itself says about who the program is for."""
    return [
        *targets,
        *(f"Stage: {stage}" for stage in stages),
        *(f"Focus: {sector}" for sector in sectors),
    ]


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
