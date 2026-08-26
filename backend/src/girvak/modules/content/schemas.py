"""
Module: girvak/modules/content/schemas.py
Layer: Schema
Purpose: The page payloads /v1/content/* returns. For a read-only projection of
         Airtable there is no second internal shape: these models are both the
         contract and the value the mapping produces.

Dependencies: none
Called by: modules/content/{router,service,home,about,fellow,people}.py
Calls: nothing
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

AccentColor = Literal["teal", "coral", "ink"]


class _Frozen(BaseModel):
    """Content is computed, then read. Nothing mutates it in place."""

    model_config = ConfigDict(frozen=True)


class CTA(_Frozen):
    """A labelled link."""

    label: str
    href: str


class SEO(_Frozen):
    """Title and description of one page."""

    title: str
    description: str


class Hero(_Frozen):
    """Home hero: static lead text plus the word the belt rotates through."""

    base_text: str
    rotator_words: list[str]
    # Split so the middle clause can carry the coral highlight.
    subhead_pre: str
    subhead_highlight: str
    subhead_post: str
    ctas: list[CTA]
    images: list[str]


class ImpactTile(_Frozen):
    """One counter tile in the 3x3 impact mosaic."""

    count: float
    decimals: int = 0
    prefix: str = ""
    suffix: str = ""
    label: str
    desc: str
    color: AccentColor
    row: int
    col: int


class WhatWeDoCard(_Frozen):
    """A flip card: front lead/sub, back eyebrow/text."""

    href: str
    image: str
    lead: str
    sub: str
    eyebrow: str
    text: str
    color: AccentColor


class Fellow(_Frozen):
    """One fellow card on the home belt."""

    year: str
    name: str
    university: str
    department: str = ""
    image: str
    color: AccentColor


class Partner(_Frozen):
    """A partner logo and where it links."""

    name: str
    logo: str
    href: str = "#"


class Partners(_Frozen):
    """The partners band."""

    headline_pre: str
    headline_highlight: str
    sub: str
    ctas: list[CTA]
    featured: Partner
    logos: list[Partner]


class FooterContact(_Frozen):
    """Address block in the footer."""

    address: str
    email: str
    phone: str
    phone_href: str


class Footer(_Frozen):
    """Footer, shared by every page."""

    newsletter_title: str
    newsletter_text: str
    brand_text: str
    explore_links: list[CTA]
    contact: FooterContact
    copyright: str


class HomeContent(_Frozen):
    """Everything the home page renders."""

    seo: SEO
    hero: Hero
    impact: list[ImpactTile]
    impact_image: str = "/images/impact-photo.jpg"
    what_we_do: list[WhatWeDoCard]
    fellows: list[Fellow]
    fellows_headline: str = "meet our fellows"
    fellows_cta: CTA = CTA(label="see all fellows", href="/fellow-program#fellows")
    partners: Partners
    footer: Footer


class Person(_Frozen):
    """One person from the Airtable `people` table.

    `first`/`last` are split from the Airtable `name`. `roles` keeps the raw
    tags (mh = trustees, yk = directors, team, fellow, alumni, challenger).
    """

    first: str
    last: str = ""
    company: str = ""
    position: str = ""
    university: str = ""
    department: str = ""
    photo: str = ""
    linkedin: str = ""
    roles: list[str] = []
    year: str = ""


class PeopleContent(_Frozen):
    """People, grouped the way the pages show them."""

    trustees: list[Person]
    directors: list[Person]
    team: list[Person]
    fellows: list[Person]
    alumni: list[Person]
    challengers: list[Person]


class AboutMission(_Frozen):
    """Mission block on the about page."""

    kicker: str
    headline: str
    image: str = ""


class AboutWwsStrip(_Frozen):
    """One "what we solve" strip."""

    label: str
    headline: str
    desc: str
    overlay_color: str
    image: str = ""
    href: str = "#"


class AboutSectionHead(_Frozen):
    """Heading pair above a people section."""

    headline: str
    subheadline: str = ""


class AboutCtaBand(_Frozen):
    """A full-width band with one call to action."""

    headline: str
    text: str
    cta_label: str
    cta_href: str = "#"


class AboutContent(_Frozen):
    """Everything the about page renders."""

    seo_title: str
    seo_description: str
    hero_html: str
    about_paragraphs: list[str]
    mission: AboutMission
    story_headline: str
    story_paragraphs: list[str]
    what_we_solve_headline: str
    what_we_solve_strips: list[AboutWwsStrip]
    trustees: AboutSectionHead
    directors: AboutSectionHead
    team: AboutSectionHead
    reports: AboutCtaBand
    work_with_us: AboutCtaBand


class FellowCta(_Frozen):
    """A call to action on the fellow-program page."""

    label: str = ""
    href: str = "#"


class FellowHowBlock(_Frozen):
    """ "How it works" block: label, paragraphs, closing kicker."""

    label: str = ""
    paragraphs: list[str] = []
    kicker: str = ""


class FellowExpectCard(_Frozen):
    """One "what to expect" card."""

    name: str = ""
    desc: str = ""
    image: str = ""
    cap: str = ""


class FellowWydItem(_Frozen):
    """One "what you'll do" item on the challenger belt."""

    text: str = ""
    image: str = ""


class FellowContent(_Frozen):
    """Fellow + Challenger program page."""

    hero_image: str = ""
    hero_headline: str = ""
    hero_headline_html: str = ""
    hero_cta_primary: FellowCta = FellowCta()
    hero_cta_secondary: FellowCta = FellowCta()
    about_html: str = ""

    application: FellowHowBlock = FellowHowBlock()
    selection: FellowHowBlock = FellowHowBlock()

    what_to_expect_headline: str = ""
    what_to_expect: list[FellowExpectCard] = []

    fellows_headline: str = ""
    fellows_cta: FellowCta = FellowCta()

    alumni_headline: str = ""
    alumni_headline_html: str = ""
    alumni_intro: str = ""
    alumni_label: str = ""
    alumni_bullets: list[str] = []
    alumni_cta: FellowCta = FellowCta()

    giveback_headline: str = ""
    giveback_headline_html: str = ""
    giveback_lead: str = ""
    giveback_body: str = ""
    giveback_cta: FellowCta = FellowCta()

    challenger_hero_image: str = ""
    challenger_hero_headline: str = ""
    challenger_hero_headline_html: str = ""
    challenger_paragraphs: list[str] = []
    challenger_cta_primary: FellowCta = FellowCta()
    challenger_cta_secondary: FellowCta = FellowCta()
    challenger_application: FellowHowBlock = FellowHowBlock()
    challenger_selection: FellowHowBlock = FellowHowBlock()

    what_youll_do_headline: str = ""
    what_youll_do: list[FellowWydItem] = []

    challengers_headline: str = ""
    challengers_cta: FellowCta = FellowCta()
