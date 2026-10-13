"""
Module: tests/modules/content/test_programs.py
Layer: Test
Purpose: The /programs page: categories become tiles in the design's order,
         approved programs land under the category they link to with their
         sector labels resolved, current before past, and drafts never show.

Dependencies: none
Called by: pytest
Calls: girvak/modules/content/programs.py
"""

from __future__ import annotations

from typing import Any

from girvak.infra.airtable.client import AirtableRecord
from girvak.modules.content import programs

DEV, ES, TALENT = "recDev", "recEs", "recTal"


def category(record_id: str, name: str, **fields: Any) -> AirtableRecord:
    return AirtableRecord(id=record_id, fields={"Name": name, **fields})


def program(name: str, cat: str, **fields: Any) -> AirtableRecord:
    payload: dict[str, Any] = {"name (en)": name, "programs": [cat], "onay": True, **fields}
    return AirtableRecord(id=f"rec{abs(hash(name)) % 10**8}", fields=payload)


CATEGORIES = [
    category(DEV, "Development Programs", description="For cooperatives."),
    category(ES, "Entrepreneurship Support Programs"),
    category(TALENT, "Talent Programs"),
]
SECTORS = [AirtableRecord(id="recAi", fields={"sectors": "ai"})]


def test_tiles_follow_the_design_order_not_airtable_order() -> None:
    content = programs.build(CATEGORIES, [], SECTORS, {})

    assert [c.slug for c in content.categories] == [
        "entrepreneurship-support-programs",
        "development-programs",
        "talent-programs",
    ]
    assert content.categories[1].description == "For cooperatives."


def test_a_program_carries_what_its_card_and_filters_read() -> None:
    row = program(
        "Fintech Fellow",
        TALENT,
        text="For tech talent.",
        sectors=["recAi"],
        **{"target group": ["tech talent", "youth"], "stage": ["idea stage"]},
        **{"current/past": "current", "discover more": "https://fintechfellow.org"},
    )

    [card] = programs.build(CATEGORIES, [row], SECTORS, {}).categories[2].programs

    assert card.name == "Fintech Fellow"
    assert card.text == "For tech talent."
    assert card.sectors == ["ai"]
    assert card.targets == ["tech talent", "youth"]
    assert card.stages == ["idea stage"]
    assert card.href == "https://fintechfellow.org"
    assert card.current is True


def test_drafts_and_programs_without_a_category_are_left_out() -> None:
    rows = [
        program("Taslak", ES, onay=False),
        AirtableRecord(id="recFellow", fields={"name (en)": "Fellow Program", "onay": True}),
    ]

    content = programs.build(CATEGORIES, rows, SECTORS, {})

    assert all(c.programs == [] for c in content.categories)


def test_current_programs_come_before_past_ones() -> None:
    rows = [
        program("Eski", ES, **{"current/past": "past"}),
        program("Yeni", ES, **{"current/past": "current"}),
    ]

    cards = programs.build(CATEGORIES, rows, SECTORS, {}).categories[0].programs

    assert [(c.name, c.current) for c in cards] == [("Yeni", True), ("Eski", False)]


def test_a_program_without_a_site_is_not_a_link_and_unsafe_links_are_dropped() -> None:
    rows = [program("Bağlantısız", ES), program("Kötü", ES, **{"discover more": "javascript:x"})]

    cards = programs.build(CATEGORIES, rows, SECTORS, {}).categories[0].programs

    assert [c.href for c in cards] == ["", ""]
