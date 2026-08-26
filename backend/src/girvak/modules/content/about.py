"""
Module: girvak/modules/content/about.py
Layer: Service
Purpose: Map the Airtable `about` table onto the about page — seed first, then
         each fragment that exists.

Dependencies: none
Called by: modules/content/service.py
Calls: modules/content/{fragments,markup,schemas}.py
"""

from __future__ import annotations

from girvak.modules.content.fragments import (
    FULL,
    Fields,
    Fragments,
    field,
    link_of,
    paragraphs,
    text,
)
from girvak.modules.content.markup import about_hero_html, strong
from girvak.modules.content.schemas import (
    AboutContent,
    AboutCtaBand,
    AboutMission,
    AboutSectionHead,
    AboutWwsStrip,
)

# The strips alternate through the brand's three overlays, in this order.
_STRIP_COLORS = ("#19BAD1", "#373D42", "#F76C53")
_STRIP_FALLBACK_IMAGES = (
    "/images/wd-talent.jpg",
    "/images/wd-entrepreneur.jpg",
    "/images/wd-commonground.jpg",
)


def build(seed: AboutContent, about: Fragments) -> AboutContent:
    """Apply Airtable's about content on top of the seed.

    Args:
        seed: The committed about content.
        about: Rows of the Airtable `about` table.

    Returns:
        The about page as it should render now.
    """
    if not about:
        return seed

    hero = about.text_of("about_aboutus_headline")
    body = about.text_of("about_aboutus_text")
    story = about.text_of("about_ourstory_text")

    return seed.model_copy(
        update={
            "seo_title": about.text_of("about_seo_title") or seed.seo_title,
            "seo_description": about.text_of("about_seo_description") or seed.seo_description,
            "hero_html": about_hero_html(hero) if hero else seed.hero_html,
            "about_paragraphs": paragraphs(body) if body else seed.about_paragraphs,
            "mission": _mission(seed.mission, about),
            "story_headline": about.text_of("about_ourstory_headline") or seed.story_headline,
            "story_paragraphs": [strong(line) for line in paragraphs(story)]
            if story
            else seed.story_paragraphs,
            "what_we_solve_headline": about.text_of("about_whatwesolve_headline")
            or seed.what_we_solve_headline,
            "what_we_solve_strips": _strips(seed.what_we_solve_strips, about),
            "trustees": _section_head(
                about,
                "about_boardoftrustees_headline",
                "about_boardoftrustees_subheadline",
                seed.trustees,
            ),
            "directors": _section_head(
                about, "about_board_headline", "about_board_subheadline", seed.directors
            ),
            "team": _section_head(
                about, "about_team_headline", "about_team_subheadline", seed.team
            ),
            "reports": _cta_band(
                about,
                "about_reports_headline",
                "about_reports_text",
                "about_reports_cta",
                seed.reports,
            ),
            "work_with_us": _cta_band(
                about,
                "about_workwithus_headline",
                "about_workwithus_text",
                "about_workwithus_cta",
                seed.work_with_us,
            ),
        }
    )


def _mission(seed: AboutMission, about: Fragments) -> AboutMission:
    row = about.row("about_mission_headline")
    kicker = about.text_of("about_mission_headline")
    headline = about.text_of("about_mission_text")
    image = about.image(row, FULL)
    if not (kicker or headline or image):
        return seed
    return AboutMission(
        kicker=kicker or seed.kicker,
        headline=headline or seed.headline,
        image=image or seed.image,
    )


def _strips(seed: list[AboutWwsStrip], about: Fragments) -> list[AboutWwsStrip]:
    strips: list[AboutWwsStrip] = []
    for index, row in enumerate(about.numbered("about_whatwesolve_")):
        label = text(field(row, "text")).title()
        headline, description = _hover_split(text(field(row, "hover text", "hover_text")), label)
        strips.append(
            AboutWwsStrip(
                label=label,
                headline=headline,
                desc=description,
                overlay_color=_STRIP_COLORS[index % 3],
                image=about.image(row, FULL) or _STRIP_FALLBACK_IMAGES[index % 3],
                href=link_of(row),
            )
        )
    return strips or seed


def _hover_split(hover: str, label: str) -> tuple[str, str]:
    """Hover copy is a headline on the first line, description on the rest."""
    if not hover:
        return label, ""
    lines = paragraphs(hover)
    if len(lines) >= 2:
        return lines[0], " ".join(lines[1:])
    return (lines[0] if lines else label), ""


def _section_head(
    about: Fragments, headline_fragment: str, sub_fragment: str, seed: AboutSectionHead
) -> AboutSectionHead:
    headline = about.text_of(headline_fragment)
    subheadline = about.text_of(sub_fragment)
    if not (headline or subheadline):
        return seed
    return AboutSectionHead(
        headline=headline or seed.headline,
        subheadline=subheadline or seed.subheadline,
    )


def _cta_band(
    about: Fragments,
    headline_fragment: str,
    text_fragment: str,
    cta_fragment: str,
    seed: AboutCtaBand,
) -> AboutCtaBand:
    headline = about.text_of(headline_fragment)
    body = about.text_of(text_fragment)
    cta_row: Fields = about.row(cta_fragment)
    label = text(field(cta_row, "text"))
    if not (headline or body or label):
        return seed
    return AboutCtaBand(
        headline=headline or seed.headline,
        text=body or seed.text,
        cta_label=label or seed.cta_label,
        cta_href=link_of(cta_row, seed.cta_href),
    )
