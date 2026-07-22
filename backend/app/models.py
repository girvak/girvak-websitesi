"""Pydantic models for home-page content.

The shapes mirror the Airtable content model described in GIRVAK-index-spec.md
(index_hero, index_impact_*, index_whatwedo_*, index_fellows_*, index_partners_*),
so swapping the seed source for a live Airtable adapter needs no model changes.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr

AccentColor = Literal["teal", "coral", "ink"]


class CTA(BaseModel):
    label: str
    href: str


class SEO(BaseModel):
    title: str
    description: str


class Hero(BaseModel):
    # Static lead text, then the animated rotating word follows it.
    base_text: str
    rotator_words: list[str]
    # Subheadline split so the middle clause can be coral-highlighted.
    subhead_pre: str
    subhead_highlight: str
    subhead_post: str
    ctas: list[CTA]
    images: list[str]  # belt photos, in order


class ImpactTile(BaseModel):
    count: float          # target value the counter animates to
    decimals: int = 0     # decimal places (e.g. 1.3 -> decimals=1)
    prefix: str = ""      # e.g. "%"
    suffix: str = ""      # e.g. "M+", "+", "x"
    label: str
    desc: str
    color: AccentColor
    row: int              # 1..3
    col: int              # 1..3


class WhatWeDoCard(BaseModel):
    href: str
    image: str
    lead: str             # front headline
    sub: str              # front subtitle
    eyebrow: str          # back eyebrow
    text: str             # back description
    color: AccentColor


class Fellow(BaseModel):
    year: str             # display string, e.g. "‘21"
    name: str
    university: str
    department: str = ""  # academic department (card back, no photo)
    image: str
    color: AccentColor


class Partner(BaseModel):
    name: str             # used as alt text
    logo: str             # image path/filename


class Partners(BaseModel):
    headline_pre: str
    headline_highlight: str
    sub: str
    ctas: list[CTA]
    featured: Partner
    logos: list[Partner]


class FooterContact(BaseModel):
    address: str
    email: str
    phone: str
    phone_href: str


class Footer(BaseModel):
    newsletter_title: str
    newsletter_text: str
    brand_text: str
    explore_links: list[CTA]
    contact: FooterContact
    copyright: str


class HomeContent(BaseModel):
    seo: SEO
    hero: Hero
    impact: list[ImpactTile]
    impact_image: str = "/images/impact-photo.jpg"
    what_we_do: list[WhatWeDoCard]
    fellows: list[Fellow]
    partners: Partners
    footer: Footer


# --- People (about page: trustees / directors / team + fellows) ---

class Person(BaseModel):
    """One person from the Airtable `people` table.

    `first`/`last` are split from the Airtable `name`; `company`/`position`
    mirror the design's PeopleGrid card. `photo`/`linkedin` are Airtable values
    (photo is a direct attachment URL). `roles` carries the raw tags
    (mh = trustees, yk = directors, fellow, team) for debugging/filtering.
    """
    first: str
    last: str = ""
    company: str = ""          # organisation
    position: str = ""         # title (board) — students have no title
    university: str = ""
    department: str = ""
    photo: str = ""            # direct Airtable attachment URL
    linkedin: str = ""
    roles: list[str] = []
    year: str = ""           # cohort / class year display, e.g. '25


class PeopleContent(BaseModel):
    trustees: list[Person]     # Airtable tag "mh"  (Mütevelli Heyeti)
    directors: list[Person]    # Airtable tag "yk"  (Yönetim Kurulu)
    team: list[Person]         # Airtable tag "team"
    fellows: list[Person]      # Airtable tag "fellow"
    alumni: list[Person]       # Airtable tag "alumni"
    challengers: list[Person]  # Airtable tag "challenger"


# --- About page (Airtable `about` table) ---

class AboutMission(BaseModel):
    kicker: str
    headline: str
    image: str = ""


class AboutWwsStrip(BaseModel):
    label: str
    headline: str
    desc: str
    overlay_color: str
    image: str = ""


class AboutSectionHead(BaseModel):
    headline: str
    subheadline: str = ""


class AboutCtaBand(BaseModel):
    headline: str
    text: str
    cta_label: str
    cta_href: str = "#"


class AboutContent(BaseModel):
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


# --- Newsletter ---

class NewsletterRequest(BaseModel):
    email: EmailStr


class NewsletterResponse(BaseModel):
    status: Literal["subscribed", "already_subscribed"]
    email: EmailStr
