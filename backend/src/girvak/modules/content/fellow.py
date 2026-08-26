"""
Module: girvak/modules/content/fellow.py
Layer: Service
Purpose: Map the Airtable `fellow` table onto the fellow-program page, which
         carries two programmes (Fellow and Challenger) in one set of tagged
         fragments. Seed first, then every fragment that exists.

Dependencies: none
Called by: modules/content/service.py
Calls: modules/content/{fragments,markup,schemas}.py
"""

from __future__ import annotations

import re

from girvak.modules.content.fragments import (
    FULL,
    Fields,
    Fragments,
    field,
    link_of,
    paragraphs,
    text,
    trailing_number,
)
from girvak.modules.content.markup import (
    alumni_headline_html,
    challenger_hero_html,
    challenger_paragraph_html,
    fellow_about_html,
    fellow_hero_html,
    giveback_headline_html,
    highlight,
    title_desc,
)
from girvak.modules.content.schemas import (
    FellowContent,
    FellowCta,
    FellowExpectCard,
    FellowHowBlock,
    FellowWydItem,
)

# The "what to expect" cards alternate their corner cut.
_EXPECT_CAPS = ("cap-top cap-left", "cap-bottom cap-right")

# Shipped icons for the challenger belt, used until Airtable carries its own.
_WYD_FALLBACK_ICONS = (
    "/images/chal-1-key.png",
    "/images/chal-2-workshop.png",
    "/images/chal-3-talk.png",
    "/images/chal-4-heads.png",
    "/images/chal-5-spark.png",
)

# Editors have written this fragment family several ways ("whatyou'lldo",
# "whatyoulldo", "whatyou’lldo"), so the name is matched loosely.
_WYD_ITEM_NAME = re.compile(r"challenger_whatyou.?ll.?do_\d+\s*$", re.I)
_WYD_HEADLINE_NAME = re.compile(r"^challenger_whatyou.?ll.?do(_headline)?\s*$", re.I)


def build(seed: FellowContent, table: Fragments) -> FellowContent:
    """Apply Airtable's fellow-program content on top of the seed.

    Args:
        seed: The committed fellow content.
        table: Rows of the Airtable `fellow` table.

    Returns:
        The fellow-program page as it should render now.
    """
    if not table:
        return seed

    # When any row is ticked `active`, that tick becomes the visibility rule for
    # the whole table; otherwise every row counts.
    active = table.where(lambda row: field(row, "active") is True)
    fellow = active if active else table

    hero_row = fellow.row("fellow_hero_headline")
    hero_headline = fellow.text_of("fellow_hero_headline")
    about_copy = fellow.text_of("fellow_about_text")
    challenger_row = fellow.row("challenger_hero_headline")
    challenger_headline = fellow.text_of("challenger_hero_headline")
    alumni_headline = fellow.text_of("fellow_alumni_headline")
    alumni_bullets = fellow.text_of("fellow_alumni_subtext")
    giveback_headline = fellow.text_of("fellow_giveback_headline")
    giveback_lead, giveback_body = _giveback_body(fellow, seed)

    return seed.model_copy(
        update={
            "hero_image": fellow.image(hero_row, FULL) or seed.hero_image,
            "hero_headline": hero_headline or seed.hero_headline,
            "hero_headline_html": fellow_hero_html(hero_headline)
            if hero_headline
            else seed.hero_headline_html,
            "hero_cta_primary": _cta(fellow, "fellow_hero_cta_primary", seed.hero_cta_primary),
            "hero_cta_secondary": _cta(
                fellow, "fellow_hero_cta_secondary", seed.hero_cta_secondary
            ),
            "about_html": _about_html(about_copy) if about_copy else seed.about_html,
            "application": _how_block(
                fellow,
                "fellow_application_1_subheadline",
                "fellow_application_1_text",
                seed.application,
            ),
            "selection": _how_block(
                fellow,
                "fellow_application_2_subheadline",
                "fellow_application_2_text",
                seed.selection,
            ),
            "what_to_expect_headline": fellow.text_of("fellow_whattoexpect_headline")
            or seed.what_to_expect_headline,
            "what_to_expect": _expect_cards(seed.what_to_expect, fellow),
            "fellows_headline": fellow.text_of("fellow_fellows_headline") or seed.fellows_headline,
            "fellows_cta": _cta(fellow, "fellow_fellows_cta", seed.fellows_cta),
            "alumni_headline": alumni_headline or seed.alumni_headline,
            "alumni_headline_html": alumni_headline_html(alumni_headline)
            if alumni_headline
            else seed.alumni_headline_html,
            "alumni_intro": fellow.text_of("fellow_alumni_text") or seed.alumni_intro,
            "alumni_label": fellow.text_of("fellow_alumni_subheadline") or seed.alumni_label,
            "alumni_bullets": paragraphs(alumni_bullets) if alumni_bullets else seed.alumni_bullets,
            "alumni_cta": _cta(fellow, "fellow_alumni_cta", seed.alumni_cta),
            "giveback_headline": giveback_headline or seed.giveback_headline,
            "giveback_headline_html": giveback_headline_html(giveback_headline)
            if giveback_headline
            else seed.giveback_headline_html,
            "giveback_lead": giveback_lead,
            "giveback_body": giveback_body,
            "giveback_cta": _cta(fellow, "fellow_giveback_cta", seed.giveback_cta),
            "challenger_hero_image": fellow.image(challenger_row, FULL)
            or seed.challenger_hero_image,
            "challenger_hero_headline": challenger_headline or seed.challenger_hero_headline,
            "challenger_hero_headline_html": challenger_hero_html(challenger_headline)
            if challenger_headline
            else seed.challenger_hero_headline_html,
            "challenger_paragraphs": _challenger_paragraphs(seed.challenger_paragraphs, fellow),
            "challenger_cta_primary": _cta(
                fellow, "challenger_hero_cta_primary", seed.challenger_cta_primary
            ),
            "challenger_cta_secondary": _cta(
                fellow, "challenger_hero_cta_secondary", seed.challenger_cta_secondary
            ),
            "challenger_application": _how_block(
                fellow,
                "challenger_application_1_subheadline",
                "challenger_application_1_text",
                seed.challenger_application,
            ),
            "challenger_selection": _how_block(
                fellow,
                "challenger_application_2_subheadline",
                "challenger_application_2_text",
                seed.challenger_selection,
            ),
            "what_youll_do_headline": _wyd_headline(fellow) or seed.what_youll_do_headline,
            "what_youll_do": _wyd_items(seed.what_youll_do, fellow),
            "challengers_headline": fellow.text_of("challenger_challengers_headline")
            or seed.challengers_headline,
            "challengers_cta": _cta(fellow, "challenger_challengers_cta", seed.challengers_cta),
        }
    )


def _about_html(copy: str) -> str:
    """Markdown emphasis when the editor used it; the design's phrases otherwise."""
    return highlight(copy) if "**" in copy else fellow_about_html(copy)


def _cta(fellow: Fragments, fragment: str, seed: FellowCta) -> FellowCta:
    row = fellow.row(fragment)
    label = text(field(row, "text"))
    if not label:
        return seed
    return FellowCta(label=label, href=link_of(row, seed.href or "#"))


def _how_block(
    fellow: Fragments, label_fragment: str, text_fragment: str, seed: FellowHowBlock
) -> FellowHowBlock:
    label = fellow.text_of(label_fragment)
    body = fellow.text_of(text_fragment)
    if not (label or body):
        return seed

    lines = paragraphs(body) if body else []
    kicker = seed.kicker
    if lines:
        last = lines[-1]
        bare = re.sub(r"[*_]", "", last).strip().lower().replace("’", "'")
        # A closing "that's it" line is the block's kicker, not a paragraph.
        if bare.startswith("that's it") or (last.startswith("**") and last.endswith("**")):
            kicker = re.sub(r"\*+", "", last).strip()
            lines = lines[:-1]

    return FellowHowBlock(
        label=label or seed.label,
        paragraphs=[highlight(line) for line in lines] or seed.paragraphs,
        kicker=kicker,
    )


def _expect_cards(seed: list[FellowExpectCard], fellow: Fragments) -> list[FellowExpectCard]:
    rows = _tagged_numbered(fellow, "fellow_whattoexpect", "fellow_whattoexpect_")
    cards: list[FellowExpectCard] = []

    for index, row in enumerate(rows):
        name, description = title_desc(text(field(row, "text")))
        hover = text(field(row, "hover text", "hover_text"))
        if hover and not description:
            description = hover
        image = fellow.image(row, FULL)
        if not name and not image:
            continue

        prior = seed[index] if index < len(seed) else None
        cards.append(
            FellowExpectCard(
                name=name or (prior.name if prior else ""),
                desc=description or (prior.desc if prior else ""),
                image=image or (prior.image if prior else ""),
                cap=_EXPECT_CAPS[index % len(_EXPECT_CAPS)],
            )
        )
    return cards or seed


def _challenger_paragraphs(seed: list[str], fellow: Fragments) -> list[str]:
    copy = fellow.text_of("challenger_hero_text")
    if not copy:
        return seed
    blocks = [block.strip() for block in re.split(r"\n\s*\n", copy) if block.strip()]
    if len(blocks) < 2:
        blocks = paragraphs(copy)
    return [challenger_paragraph_html(block) for block in blocks]


def _giveback_body(fellow: Fragments, seed: FellowContent) -> tuple[str, str]:
    copy = fellow.text_of("fellow_giveback_text")
    if not copy:
        return seed.giveback_lead, seed.giveback_body
    lines = paragraphs(copy)
    if not lines:
        return seed.giveback_lead, seed.giveback_body
    body = " ".join(lines[1:]) if len(lines) > 1 else seed.giveback_body
    return lines[0], body


def _wyd_headline(fellow: Fragments) -> str:
    for fragment in ("challenger_whatyou'lldo_headline", "challenger_whatyou'lldo"):
        headline = fellow.text_of(fragment)
        if headline:
            return headline
    for row in fellow.rows:
        if _WYD_HEADLINE_NAME.match(text(field(row, "name"))):
            headline = text(field(row, "text"))
            if headline:
                return headline
    return ""


def _wyd_items(seed: list[FellowWydItem], fellow: Fragments) -> list[FellowWydItem]:
    rows = [row for row in fellow.rows if _WYD_ITEM_NAME.match(text(field(row, "name")))]
    rows.sort(key=lambda row: trailing_number(text(field(row, "name"))))
    if not rows:
        rows = _tagged_numbered(fellow, "challenger_whatyou'lldo", "challenger_whatyou'lldo_")
    if not rows:
        return seed

    items: list[FellowWydItem] = []
    for index, row in enumerate(rows):
        prior = seed[index] if index < len(seed) else None
        fallback = _WYD_FALLBACK_ICONS[index] if index < len(_WYD_FALLBACK_ICONS) else ""
        image = fellow.image(row, FULL) or _icon_url(row)
        items.append(
            FellowWydItem(
                text=text(field(row, "text")) or (prior.text if prior else ""),
                image=image or (prior.image if prior else fallback),
            )
        )
    return items


def _icon_url(fields: Fields) -> str:
    """Some rows carry the icon as a plain URL instead of an attachment."""
    candidate = text(field(fields, "photo", "image", "icon", "url"))
    return candidate if candidate.startswith("http") else ""


def _tagged_numbered(fellow: Fragments, tag: str, name_prefix: str) -> list[Fields]:
    """Numbered cards inside one tag family, excluding its headline row."""
    tagged = fellow.with_tag(tag)
    strict_name = re.compile(re.escape(name_prefix) + r"\d+\s*$")
    strict = [row for row in tagged if strict_name.match(text(field(row, "name")))]
    if strict:
        return sorted(strict, key=lambda row: trailing_number(text(field(row, "name"))))

    loose = [
        row
        for row in tagged
        if re.search(r"_\d+\s*$", text(field(row, "name")))
        and "headline" not in text(field(row, "name")).lower()
    ]
    return sorted(loose, key=lambda row: trailing_number(text(field(row, "name"))))
