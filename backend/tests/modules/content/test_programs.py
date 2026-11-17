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

import pytest

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
PARTNERS = [
    AirtableRecord(
        id="recTskb", fields={"name": "TSKB Bank", "link": "https://tskb.com.tr", "onay": True}
    ),
    AirtableRecord(id="recOther", fields={"name": "Another bank"}),
]


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


def test_a_program_page_uses_the_committed_copy_where_the_row_has_nothing() -> None:
    content = programs.build(CATEGORIES, [program("TSKB Co-Venture", ES)], SECTORS, {}, PARTNERS)

    card = content.categories[0].programs[0]
    assert card.slug == "tskb-co-venture"
    assert len(card.stats) == 4
    assert (card.stats[0].value, card.stats[0].label) == (12, "month journey")
    assert card.stats[2].prefix == "%"
    assert len(card.for_who) == 3
    assert len(card.what_happens) == 4
    assert [(p.name, p.href) for p in card.partners] == [("TSKB Bank", "https://tskb.com.tr")]
    assert '<span class="hl">TSKB Co-Venture</span>' in card.body_html[0]


def test_what_the_row_says_wins_over_the_committed_copy() -> None:
    content = programs.build(
        CATEGORIES,
        [
            program(
                "TSKB Co-Venture",
                ES,
                text="Short card line.",
                **{"program overview": "A **new** overview.\nSecond paragraph."},
                **{
                    "for who": "• Founders\n- Teams\n\nStudents",
                    "what happens": "Workshops",
                    "partner": ["recOther"],
                    "data1": "20 months\nLonger now.\n",
                },
            )
        ],
        SECTORS,
        {},
        PARTNERS,
    )

    card = content.categories[0].programs[0]
    assert card.body_html == ['A <span class="hl">new</span> overview.', "Second paragraph."]
    assert card.for_who == ["Founders", "Teams", "Students"]
    assert card.what_happens == ["Workshops"]
    assert [p.name for p in card.partners] == ["Another bank"]
    assert [(s.value, s.label, s.text) for s in card.stats] == [(20, "months", "Longer now.")]


def test_a_program_with_no_committed_copy_shows_only_what_the_row_holds() -> None:
    content = programs.build(
        CATEGORIES,
        [
            program(
                "Brand New Program",
                DEV,
                text="Short card line.",
                **{
                    "program overview": "Plain overview.",
                    "target group": ["Women"],
                    "stage": ["Early"],
                },
            )
        ],
        SECTORS,
        {},
    )

    card = next(c for c in content.categories if c.slug == "development-programs").programs[0]
    assert card.body_html == ["Plain overview."]
    assert card.stats == []
    assert card.what_happens == []
    assert card.partners == []
    assert card.for_who == ["Women", "Stage: Early"]


def test_the_card_text_and_the_page_overview_are_different_columns() -> None:
    content = programs.build(
        CATEGORIES,
        [
            program(
                "Brand New Program",
                DEV,
                text="Short card line.",
                **{"program overview": "The long text over the photo."},
            )
        ],
        SECTORS,
        {},
    )

    card = next(c for c in content.categories if c.slug == "development-programs").programs[0]
    assert card.text == "Short card line."
    assert card.body_html == ["The long text over the photo."]


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        # The shapes editors have actually written.
        (
            "27 ventures\nteams supported from idea to scale.\n",
            (27, "", "", "ventures", "teams supported from idea to scale.", False),
        ),
        ("12–85 age range\nno age limit.\n", (12, "", "–85", "age range", "no age limit.", False)),
        (
            "1,076 total applicants\nfrom 53 cities.\n",
            (1076, "", "", "total applicants", "from 53 cities.", True),
        ),
        ("100% employment rate\n", (100, "", "%", "employment rate", "", False)),
        ("50+ events\n", (50, "", "+", "events", "", False)),
        ("20,000 TL monthly scholarship\n", (20000, "", "", "TL monthly scholarship", "", True)),
        ("Since 2016\nfive cohorts.\n", (2016, "Since ", "", "", "five cohorts.", False)),
        (
            "3,143 total products\n\nbuilt across the Ideathon.\n",
            (3143, "", "", "total products", "built across the Ideathon.", True),
        ),
    ],
)
def test_a_data_box_is_read_the_way_it_is_written(
    cell: str, expected: tuple[float, str, str, str, str, bool]
) -> None:
    box = programs.parse_data_box(cell)

    assert box is not None
    assert (box.value, box.prefix, box.suffix, box.label, box.text, box.grouped) == expected


@pytest.mark.parametrize("cell", ["", "\n\n", "No figure here\nat all."])
def test_a_cell_without_a_figure_is_not_a_box(cell: str) -> None:
    assert programs.parse_data_box(cell) is None


def test_the_four_boxes_come_from_data1_to_data4_in_order() -> None:
    content = programs.build(
        CATEGORIES,
        [
            program(
                "Counted",
                DEV,
                data1="27 ventures\nthe first.",
                data2="",
                **{"data3": "5 years\nthe third.", "data 4": "9 cities"},
            )
        ],
        SECTORS,
        {},
    )

    card = next(c for c in content.categories if c.slug == "development-programs").programs[0]
    assert [(b.value, b.label) for b in card.stats] == [
        (27, "ventures"),
        (5, "years"),
        (9, "cities"),
    ]
