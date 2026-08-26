"""
Module: girvak/modules/content/people.py
Layer: Service
Purpose: Map the Airtable `people` table onto the groups the pages show, in the
         order they show them: Turkish alphabetical, with the board's chair and
         vice-chair first. Also builds the home page's fellow belt.

Dependencies: none
Called by: modules/content/service.py
Calls: modules/content/fragments.py, modules/content/markup.py
"""

from __future__ import annotations

import random
import re

from girvak.modules.content.fragments import (
    LARGE,
    Fields,
    Fragments,
    field,
    tags,
    text,
)
from girvak.modules.content.markup import format_year
from girvak.modules.content.schemas import Fellow, PeopleContent, Person

# Airtable tag -> the group a page renders. `mh` = Mütevelli Heyeti (trustees),
# `yk` = Yönetim Kurulu (board of directors).
TRUSTEES_TAG = "mh"
DIRECTORS_TAG = "yk"
TEAM_TAG = "team"
FELLOW_TAG = "fellow"
ALUMNI_TAG = "alumni"
CHALLENGER_TAG = "challenger"

# Editors' spellings that mean the same group.
_TAG_ALIASES: dict[str, frozenset[str]] = {
    CHALLENGER_TAG: frozenset({"challenger", "challengers", "challlenger"}),
    TEAM_TAG: frozenset({"team", "ekip", "staff"}),
}

# The board list opens with the chair and the vice-chair; everyone else is
# alphabetical. Matched on first name because that is what Airtable holds.
_DIRECTOR_PRIORITY = ("sina", "yomi")

# Home belt colour rotation.
_PALETTE: tuple[str, str, str] = ("teal", "coral", "ink")

# Turkish collation, done in code rather than through a system locale: a
# container image without tr_TR.UTF-8 would silently fall back to ASCII order
# and put Ş after Z.
_ALPHABET = "abcçdefgğhıijklmnoöprsştuüvyz"
_UPPER_TO_LOWER = str.maketrans(
    {
        "I": "ı",
        "İ": "i",
        "Ş": "ş",
        "Ğ": "ğ",
        "Ü": "ü",
        "Ö": "ö",
        "Ç": "ç",
    }
)
_ORDER = {letter: index for index, letter in enumerate(_ALPHABET)}
_AFTER_ALPHABET = len(_ALPHABET)

_YEAR_FIELDS = (
    "year",
    "cohort",
    "dönem",
    "donem",
    "period",
    "class",
    "fellow_year",
    "fellow year",
)


def build(people: Fragments) -> PeopleContent:
    """Group every person the way the pages read them.

    Args:
        people: Rows of the Airtable `people` table.

    Returns:
        Trustees, directors, team, fellows, alumni, and challengers.
    """
    return PeopleContent(
        trustees=_alphabetical(_persons(people, TRUSTEES_TAG)),
        directors=_directors_first(_persons(people, DIRECTORS_TAG)),
        team=_alphabetical(_persons(people, TEAM_TAG)),
        fellows=_alphabetical(_persons(people, FELLOW_TAG)),
        alumni=_alphabetical(_persons(people, ALUMNI_TAG)),
        challengers=_alphabetical(_persons(people, CHALLENGER_TAG)),
    )


def fellow_pool(people: Fragments) -> list[Fellow]:
    """Fellows eligible for the home page belt: they need a name and a photo.

    Args:
        people: Rows of the Airtable `people` table.

    Returns:
        Every eligible fellow, unshuffled.
    """
    pool: list[Fellow] = []
    for row in _rows_with_tag(people, FELLOW_TAG):
        name = text(field(row, "name"))
        photo = people.image(row, LARGE, "photo", "attachments", "image")
        if not name or not photo:
            continue
        pool.append(
            Fellow(
                year=year_of(row),
                name=name,
                university=text(field(row, "university")),
                department=text(field(row, "department")),
                image=photo,
                color="teal",
            )
        )
    return pool


def spotlight(pool: list[Fellow], count: int) -> list[Fellow]:
    """Pick the belt for one render, rotating the accent colours.

    The belt is deliberately different on each render — it is a sample of the
    cohort, not a ranking.

    Args:
        pool: Every eligible fellow.
        count: How many cards the belt shows.

    Returns:
        The chosen fellows, coloured in palette order.
    """
    if not pool:
        return []
    size = max(1, min(count, len(pool)))
    picked = random.sample(pool, size)  # display order, not a secret
    return [
        fellow.model_copy(update={"color": _PALETTE[index % len(_PALETTE)]})
        for index, fellow in enumerate(picked)
    ]


def people_spotlight(pool: list[Person], count: int) -> list[Person]:
    """Same belt, when the cards come from person rows instead.

    Args:
        pool: Candidate people (they must have a photo).
        count: How many cards to show.

    Returns:
        The chosen people.
    """
    if not pool:
        return []
    size = max(1, min(count, len(pool)))
    return random.sample(pool, size)  # display order, not a secret


def year_of(fields: Fields) -> str:
    """Cohort year of a person, from a field or from a tag like `fellow_21`.

    Args:
        fields: One person row's fields.

    Returns:
        The display year, empty when unknown.
    """
    raw = text(field(fields, *_YEAR_FIELDS))
    if raw:
        return format_year(raw)
    for tag in tags(fields):
        match = re.search(r"(?:^|_|-)(['’]?)(\d{2})$", str(tag))
        if match:
            return format_year(match.group(2))
    return ""


def sort_key(value: str) -> tuple[int, ...]:
    """Turkish alphabetical sort key.

    Args:
        value: A name.

    Returns:
        Letter positions in the Turkish alphabet; unknown characters sort last.
    """
    folded = value.translate(_UPPER_TO_LOWER).casefold()
    return tuple(_ORDER.get(char, _AFTER_ALPHABET) for char in folded)


def _persons(people: Fragments, tag: str) -> list[Person]:
    return [_person(people, row) for row in _rows_with_tag(people, tag)]


def _person(people: Fragments, fields: Fields) -> Person:
    first, last = _split_name(text(field(fields, "name")))
    return Person(
        first=first,
        last=last,
        company=text(field(fields, "organisation", "organization", "company")),
        position=text(field(fields, "title", "position")),
        university=text(field(fields, "university")),
        department=text(field(fields, "department")),
        photo=people.image(fields, LARGE, "photo", "attachments", "image"),
        linkedin=_linkedin(field(fields, "linkedin")),
        roles=tags(fields),
        year=year_of(fields),
    )


def _rows_with_tag(people: Fragments, tag: str) -> list[Fields]:
    aliases = _TAG_ALIASES.get(tag, frozenset({tag}))
    return [
        row
        for row in people.rows
        if any(str(item).lower() in aliases for item in tags(row)) and text(field(row, "name"))
    ]


def _alphabetical(people: list[Person]) -> list[Person]:
    return sorted(people, key=lambda person: sort_key(_full_name(person)))


def _directors_first(people: list[Person]) -> list[Person]:
    return sorted(people, key=lambda person: (_priority(person), sort_key(_full_name(person))))


def _priority(person: Person) -> int:
    first = person.first.casefold().strip()
    full = _full_name(person).casefold()
    for index, key in enumerate(_DIRECTOR_PRIORITY):
        if first == key or full.startswith(f"{key} "):
            return index
    return len(_DIRECTOR_PRIORITY)


def _full_name(person: Person) -> str:
    return f"{person.first} {person.last}".strip()


def _split_name(name: str) -> tuple[str, str]:
    """`Deniz Hale Durakbaşı` becomes (`Deniz Hale`, `Durakbaşı`)."""
    parts = name.split()
    if len(parts) <= 1:
        return name, ""
    return " ".join(parts[:-1]), parts[-1]


def _linkedin(value: object) -> str:
    """First real LinkedIn profile URL; a bare linkedin.com link is dropped."""
    raw = text(value)
    if not raw:
        return ""
    for candidate in re.split(r"\s+", raw):
        cleaned = candidate.strip().rstrip(".,;")
        if not cleaned:
            continue
        if "linkedin.com" not in cleaned.lower() and not cleaned.startswith("http"):
            continue
        if not re.match(r"^https?://", cleaned, re.I):
            cleaned = "https://" + cleaned.lstrip("/")
        if re.search(r"linkedin\.com/in/", cleaned, re.I):
            return cleaned
    return ""
