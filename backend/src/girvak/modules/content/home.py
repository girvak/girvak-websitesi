"""
Module: girvak/modules/content/home.py
Layer: Service
Purpose: Map the Airtable `home` and `partner` tables onto the home page. Seed
         first, then override each section Airtable actually provides — a
         missing fragment keeps the shipped copy instead of blanking a band.

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
    text,
    trailing_number,
)
from girvak.modules.content.markup import eyebrow, parse_stat, split_lead, split_subhead
from girvak.modules.content.schemas import (
    CTA,
    SEO,
    Footer,
    Hero,
    HomeContent,
    ImpactTile,
    Partner,
    Partners,
    WhatWeDoCard,
)

_PALETTE: tuple[str, str, str] = ("teal", "coral", "ink")
_EXPLORE_NAME = re.compile(r"index_footer_explore_\d+\s*$")

# Footer fragment -> which footer field it fills.
_FOOTER_FIELDS = {
    "index_footer_newsletter_title": "newsletter_title",
    "index_footer_newsletter_text": "newsletter_text",
    "index_footer_brand_text": "brand_text",
    "index_footer_copyright": "copyright",
}
_FOOTER_CONTACT_FIELDS = {
    "index_footer_address": "address",
    "index_footer_email": "email",
    "index_footer_phone": "phone",
    "index_footer_phone_href": "phone_href",
}


def build(seed: HomeContent, home: Fragments, partner: Fragments) -> HomeContent:
    """Apply Airtable's home content on top of the seed.

    The fellow belt is not filled here: it is sampled per render from the people
    table (modules/content/people.py).

    Args:
        seed: The committed home content.
        home: Rows of the Airtable `home` table.
        partner: Rows of the Airtable `partner` table.

    Returns:
        The home page as it should render now.
    """
    return seed.model_copy(
        update={
            "seo": _seo(seed.seo, home),
            "hero": _hero(seed.hero, home),
            "impact": _impact(seed.impact, home),
            "impact_image": _impact_image(seed.impact_image, home),
            "what_we_do": _what_we_do(seed.what_we_do, home),
            "fellows_headline": home.text_of("index_fellows_headline") or seed.fellows_headline,
            "fellows_cta": _cta(home, "index_fellows_cta", seed.fellows_cta),
            "partners": _partners(seed.partners, home, partner),
            "footer": _footer(seed.footer, home),
        }
    )


def _seo(seed: SEO, home: Fragments) -> SEO:
    return SEO(
        title=home.text_of("index_seo_title") or seed.title,
        description=home.text_of("index_seo_description") or seed.description,
    )


def _hero(seed: Hero, home: Fragments) -> Hero:
    row = home.row("index_hero_image")
    images = home.images(row, FULL) or seed.images

    # Headline and rotator words stay on the seed's split: Airtable's
    # `index_hero_headline` is one line, and pasting it in breaks the rotator.
    subhead_pre, subhead_highlight, subhead_post = split_subhead(
        home.text_of("index_hero_subheadline"),
        (seed.subhead_pre, seed.subhead_highlight, seed.subhead_post),
    )

    return seed.model_copy(
        update={
            "images": images,
            "ctas": _hero_ctas(seed, home),
            "subhead_pre": subhead_pre,
            "subhead_highlight": subhead_highlight,
            "subhead_post": subhead_post,
        }
    )


def _hero_ctas(seed: Hero, home: Fragments) -> list[CTA]:
    primary_label = home.text_of("index_hero_cta_primary")
    secondary_label = home.text_of("index_hero_cta_secondary")
    if not (primary_label or secondary_label):
        return seed.ctas

    # The design renders the secondary CTA first.
    ctas: list[CTA] = []
    if secondary_label:
        fallback = seed.ctas[0].href if seed.ctas else "#"
        ctas.append(
            CTA(label=secondary_label, href=link_of(home.row("index_hero_cta_secondary"), fallback))
        )
    if primary_label:
        fallback = seed.ctas[1].href if len(seed.ctas) > 1 else "#wwd"
        ctas.append(
            CTA(label=primary_label, href=link_of(home.row("index_hero_cta_primary"), fallback))
        )
    return ctas


def _impact(seed: list[ImpactTile], home: Fragments) -> list[ImpactTile]:
    # Rows that do not parse as a statistic (index_impact_image, for one) are
    # dropped before positions are assigned, so the 3x3 grid stays intact.
    parsed = [(row, parse_stat(text(field(row, "text")))) for row in home.family("index_impact_")]
    stats = [(row, stat) for row, stat in parsed if stat is not None]

    tiles = [
        ImpactTile(
            count=count,
            decimals=decimals,
            prefix="",
            suffix=suffix,
            label=label,
            desc=text(field(row, "hover text", "hover_text")),
            color=_PALETTE[index % 3],
            row=index // 3 + 1,
            col=index % 3 + 1,
        )
        for index, (row, (count, decimals, suffix, label)) in enumerate(stats)
    ]
    return tiles or seed


def _impact_image(seed: str, home: Fragments) -> str:
    row = home.row("index_impact_image")
    return home.image(row, FULL) or seed if row else seed


def _what_we_do(seed: list[WhatWeDoCard], home: Fragments) -> list[WhatWeDoCard]:
    cards: list[WhatWeDoCard] = []
    for index, row in enumerate(home.family("index_whatwedo_")):
        copy = text(field(row, "text"))
        if not copy:
            continue

        lead, subtitle = split_lead(copy)
        prior = seed[index] if index < len(seed) else None
        image = home.image(row, FULL) or (prior.image if prior else "")
        link = text(field(row, "link", "url", "href", "external link", "external_link"))

        cards.append(
            WhatWeDoCard(
                href=link or (prior.href if prior else "#"),
                image=image,
                lead=lead,
                sub=subtitle,
                eyebrow=eyebrow(subtitle),
                text=text(field(row, "hover text", "hover_text")) or (prior.text if prior else ""),
                color=prior.color if prior else _PALETTE[index % 3],
            )
        )
    return cards or seed


def _partners(seed: Partners, home: Fragments, partner: Fragments) -> Partners:
    headline = home.text_of("index_partners_headline")
    headline_pre, headline_highlight = seed.headline_pre, seed.headline_highlight
    if headline:
        # The design highlights the last clause, so the copy is split on its
        # final comma.
        parts = headline.rsplit(",", 1)
        if len(parts) == 2:
            headline_pre, headline_highlight = parts[0] + ", ", parts[1].strip()
        else:
            headline_pre, headline_highlight = headline, ""

    featured, logos = _partner_logos(partner)

    return seed.model_copy(
        update={
            "headline_pre": headline_pre,
            "headline_highlight": headline_highlight,
            "sub": home.text_of("index_partners_text") or seed.sub,
            "featured": featured or seed.featured,
            "logos": logos or seed.logos,
        }
    )


def _partner_logos(partner: Fragments) -> tuple[Partner | None, list[Partner]]:
    featured: Partner | None = None
    logos: list[Partner] = []

    for row in partner.rows:
        if not _approved(row):
            continue
        name = text(field(row, "organization", "organisation", "name"))
        logo = partner.logo(row)
        if not name or not logo:
            continue

        entry = Partner(name=name, logo=logo, href=link_of(row))
        if _is_main(row) and featured is None:
            featured = entry
        else:
            logos.append(entry)

    logos.sort(key=lambda item: item.name.casefold())
    return featured, logos


def _approved(fields: Fields) -> bool:
    """Only rows the partner team ticked appear on the site."""
    return field(fields, "onay", "approved", "approval") is True


def _is_main(fields: Fields) -> bool:
    value = field(fields, "Tags", "tags") or []
    return isinstance(value, list) and any("main" in str(item).lower() for item in value)


def _footer(seed: Footer, home: Fragments) -> Footer:
    updates: dict[str, object] = {}
    for fragment, attribute in _FOOTER_FIELDS.items():
        value = home.text_of(fragment)
        if value:
            updates[attribute] = value

    contact_updates: dict[str, object] = {}
    for fragment, attribute in _FOOTER_CONTACT_FIELDS.items():
        value = home.text_of(fragment)
        if value:
            contact_updates[attribute] = value
    if contact_updates:
        updates["contact"] = seed.contact.model_copy(update=contact_updates)

    explore = [
        CTA(label=text(field(row, "text")), href=link_of(row))
        for row in sorted(
            (row for row in home.rows if _EXPLORE_NAME.match(text(field(row, "name")))),
            key=lambda row: trailing_number(text(field(row, "name"))),
        )
        if text(field(row, "text"))
    ]
    if explore:
        updates["explore_links"] = explore

    return seed.model_copy(update=updates) if updates else seed


def _cta(home: Fragments, fragment: str, seed: CTA) -> CTA:
    label = home.text_of(fragment)
    if not label:
        return seed
    return CTA(label=label, href=link_of(home.row(fragment), seed.href))
