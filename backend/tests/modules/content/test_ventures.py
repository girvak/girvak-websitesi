"""
Module: tests/modules/content/test_ventures.py
Layer: Test
Purpose: The founders & ventures mapping: what gets published, what the links
         resolve to, and the paging and filtering rules the page depends on.

Dependencies: none
Called by: pytest
Calls: girvak/modules/content/ventures.py
"""

from __future__ import annotations

from typing import Any

import pytest

from girvak.infra.airtable.client import AirtableRecord
from girvak.modules.content import seeds
from girvak.modules.content.schemas import VenturesCopy
from girvak.modules.content.ventures import (
    MAX_PER_PAGE,
    VenturesData,
    build,
    media_refs,
    select,
    slugify,
    year_slug,
)

AI = "recSectorAi"
FOOD = "recSectorFood"
ZEMIN = "recProgramZemin"
TERRA = "recProgramTerra"


def venture(record_id: str, name: str, **fields: Any) -> AirtableRecord:
    """One `ventures` row, approved unless the test says otherwise."""
    payload: dict[str, Any] = {"name": name, "onay": True}
    payload.update(fields)
    return AirtableRecord(id=record_id, fields=payload)


def sectors() -> list[AirtableRecord]:
    return [
        AirtableRecord(id=AI, fields={"sectors": "ai"}),
        AirtableRecord(id=FOOD, fields={"sectors": "ag-tech / food-tech"}),
    ]


def programs() -> list[AirtableRecord]:
    return [
        AirtableRecord(id=ZEMIN, fields={"name (en)": "Zemin360", "name (tr)": "Zemin360"}),
        AirtableRecord(id=TERRA, fields={"name (en)": "Terra Future Labs"}),
    ]


def people() -> list[AirtableRecord]:
    return [
        AirtableRecord(
            id="recFounderA",
            fields={
                "name": "Ayşe Yılmaz",
                "year": "2026",
                "title": "Co-founder",
                "linkedin": "https://www.linkedin.com/in/ayse",
                "photo": [
                    {
                        "id": "attAyse",
                        "url": "https://v5.airtableusercontent.com/a/large.png",
                        "filename": "a.png",
                        "type": "image/png",
                    }
                ],
            },
        ),
        AirtableRecord(
            id="recFounderB", fields={"name": "Berk Demir", "title": "CEO", "year": "2024"}
        ),
    ]


def mapped(*records: AirtableRecord, copy: VenturesCopy | None = None) -> VenturesData:
    return build(
        copy or seeds.ventures(),
        list(records),
        sectors(),
        programs(),
        people(),
        {},
    )


# --- what gets published ------------------------------------------------------


def test_a_row_without_onay_is_not_published() -> None:
    data = mapped(
        venture("rec1", "Published"),
        AirtableRecord(id="rec2", fields={"name": "Draft"}),
    )

    assert [item.name for item in data.items] == ["Published"]


def test_a_row_without_a_name_is_skipped() -> None:
    data = mapped(venture("rec1", ""), venture("rec2", "Real"))

    assert [item.name for item in data.items] == ["Real"]


def test_ventures_are_turkish_alphabetical() -> None:
    data = mapped(
        venture("rec1", "Zemin"),
        venture("rec2", "Çınar"),
        venture("rec3", "Ada"),
    )

    assert [item.name for item in data.items] == ["Ada", "Çınar", "Zemin"]


# --- the links ----------------------------------------------------------------


def test_sector_links_resolve_to_labels_and_slugs() -> None:
    data = mapped(venture("rec1", "Kybele", sectors=[FOOD, AI]))

    assert data.items[0].sectors == ["ag-tech / food-tech", "ai"]
    assert data.items[0].sector_slugs == ["ag-tech-food-tech", "ai"]


def test_program_lookup_resolves_to_the_english_name() -> None:
    data = mapped(venture("rec1", "Jobtogo", program=[ZEMIN, TERRA]))

    assert data.items[0].programs == ["Zemin360", "Terra Future Labs"]
    assert data.items[0].program_slugs == ["zemin360", "terra-future-labs"]


def test_an_unlinked_sector_falls_back_to_the_other_facet() -> None:
    data = mapped(venture("rec1", "Odd", **{"other sector": "quantum knitting"}))

    assert data.items[0].sectors == ["other"]


def test_founders_come_from_the_linked_people_rows() -> None:
    data = mapped(venture("rec1", "Yummate", people=["recFounderA", "recFounderB"]))

    founders = data.items[0].founders
    assert [founder.name for founder in founders] == ["Ayşe Yılmaz", "Berk Demir"]
    assert founders[0].title == "Co-founder"
    assert founders[0].linkedin == "https://www.linkedin.com/in/ayse"


def test_a_founder_link_that_points_nowhere_is_dropped() -> None:
    data = mapped(venture("rec1", "Ghost", people=["recMissing"]))

    assert data.items[0].founders == []


def test_a_logo_uses_the_colour_column_and_the_white_one_separately() -> None:
    data = mapped(
        venture(
            "rec1",
            "Logos",
            **{
                "logo (renkli)": [
                    {
                        "id": "attC",
                        "url": "https://v5.airtableusercontent.com/c/full.png",
                        "filename": "c.png",
                        "type": "image/png",
                    }
                ],
                "logo (beyaz)": [
                    {
                        "id": "attW",
                        "url": "https://v5.airtableusercontent.com/w/full.png",
                        "filename": "w.png",
                        "type": "image/png",
                    }
                ],
            },
        )
    )

    assert data.items[0].logo.endswith("c/full.png")
    assert data.items[0].logo_white.endswith("w/full.png")


# --- the details editors get wrong --------------------------------------------


def test_a_bare_host_becomes_an_absolute_url() -> None:
    data = mapped(venture("rec1", "Yummate", websitesi="yummate.co"))

    assert data.items[0].website == "https://yummate.co"


def test_a_full_url_is_left_alone() -> None:
    data = mapped(venture("rec1", "Algofact", websitesi="https://algofact.tech"))

    assert data.items[0].website == "https://algofact.tech"


def test_a_javascript_url_never_reaches_an_href() -> None:
    data = mapped(venture("rec1", "Nope", websitesi="javascript:alert(1)"))

    assert data.items[0].website == ""


def test_two_ventures_with_the_same_name_get_distinct_slugs() -> None:
    data = mapped(venture("rec1", "Aynı"), venture("rec2", "Aynı"))

    assert {item.slug for item in data.items} == {"ayni", "ayni-2"}


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("ag-tech / food-tech", "ag-tech-food-tech"),
        ("Yapay Zekâ", "yapay-zeka"),
        ("ÜNLÜ & Co", "unlu-co"),
        ("   ", ""),
    ],
)
def test_slugify_survives_turkish_and_punctuation(label: str, expected: str) -> None:
    assert slugify(label) == expected


# --- paging -------------------------------------------------------------------


def directory(count: int) -> VenturesData:
    return mapped(*(venture(f"rec{i}", f"Venture {i:02d}") for i in range(count)))


def test_a_page_holds_per_page_items_and_reports_the_total() -> None:
    result = select(directory(34), page=1, per_page=12)

    assert len(result.items) == 12
    assert result.page.total == 34
    assert result.page.total_pages == 3
    assert result.page.has_prev is False
    assert result.page.has_next is True


def test_the_last_page_holds_the_remainder() -> None:
    result = select(directory(34), page=3, per_page=12)

    assert len(result.items) == 10
    assert result.page.has_prev is True
    assert result.page.has_next is False


def test_pages_do_not_overlap_or_skip() -> None:
    data = directory(34)

    seen = [
        item.slug for page in (1, 2, 3) for item in select(data, page=page, per_page=12).items
    ]

    assert seen == [item.slug for item in data.items]


def test_a_page_past_the_end_lands_on_the_last_one() -> None:
    result = select(directory(34), page=99, per_page=12)

    assert result.page.page == 3
    assert result.items


def test_a_page_below_one_lands_on_the_first() -> None:
    result = select(directory(5), page=0, per_page=12)

    assert result.page.page == 1


def test_per_page_is_capped() -> None:
    result = select(directory(60), per_page=10_000)

    assert result.page.per_page == MAX_PER_PAGE
    assert len(result.items) == MAX_PER_PAGE


def test_an_empty_directory_is_one_empty_page() -> None:
    result = select(directory(0))

    assert result.items == []
    assert result.page.total == 0
    assert result.page.total_pages == 1
    assert result.page.has_next is False


# --- filtering ----------------------------------------------------------------


def filtered_fixture() -> VenturesData:
    return mapped(
        venture("rec1", "Algofact", sectors=[AI], program=[ZEMIN]),
        venture("rec2", "Kybele", sectors=[FOOD], program=[TERRA]),
        venture("rec3", "Yummate", sectors=[FOOD], program=[TERRA], people=["recFounderA"]),
        venture("rec4", "Jobtogo", sectors=[AI], program=[TERRA]),
    )


def test_one_sector_narrows_the_list() -> None:
    result = select(filtered_fixture(), sectors=["ai"])

    assert {item.name for item in result.items} == {"Algofact", "Jobtogo"}


def test_two_sectors_widen_it() -> None:
    result = select(filtered_fixture(), sectors=["ai", "ag-tech-food-tech"])

    assert result.page.total == 4


def test_sector_and_program_narrow_each_other() -> None:
    result = select(filtered_fixture(), sectors=["ai"], programs=["terra-future-labs"])

    assert [item.name for item in result.items] == ["Jobtogo"]


def test_an_unknown_slug_matches_nothing_rather_than_everything() -> None:
    result = select(filtered_fixture(), sectors=["does-not-exist"])

    assert result.items == []


def test_search_matches_a_founder_name() -> None:
    result = select(filtered_fixture(), q="Ayşe")

    assert [item.name for item in result.items] == ["Yummate"]


def test_search_ignores_case_and_turkish_diacritics() -> None:
    result = select(filtered_fixture(), q="ayse")

    assert [item.name for item in result.items] == ["Yummate"]


def test_the_filter_is_echoed_back_normalised() -> None:
    result = select(filtered_fixture(), sectors=["AI", "ai"], q="  Kybele  ")

    assert result.selected.sectors == ["ai"]
    assert result.selected.q == "Kybele"


# --- facets -------------------------------------------------------------------


def test_facets_count_the_whole_directory_when_nothing_is_selected() -> None:
    result = select(filtered_fixture())

    counts = {facet.value: facet.count for facet in result.sectors}
    assert counts == {"ai": 2, "ag-tech-food-tech": 2}


def test_a_program_filter_narrows_the_sector_counts() -> None:
    result = select(filtered_fixture(), programs=["zemin360"])

    counts = {facet.value: facet.count for facet in result.sectors}
    assert counts == {"ai": 1}


def test_a_sector_filter_does_not_narrow_its_own_counts() -> None:
    """Otherwise the facet a visitor just picked would drop to its own subset
    and the other choices in that dimension would vanish."""
    result = select(filtered_fixture(), sectors=["ai"])

    counts = {facet.value: facet.count for facet in result.sectors}
    assert counts == {"ai": 2, "ag-tech-food-tech": 2}


def test_facets_keep_the_label_the_editor_typed() -> None:
    result = select(filtered_fixture())

    labels = {facet.value: facet.label for facet in result.sectors}
    assert labels["ag-tech-food-tech"] == "ag-tech / food-tech"


# --- cohort year --------------------------------------------------------------


def test_a_founders_cohort_becomes_the_ventures_year() -> None:
    data = mapped(venture("rec1", "Yummate", people=["recFounderA"]))

    assert data.items[0].year == "’26"
    assert data.items[0].founders[0].year == "’26"


def test_the_year_comes_from_the_first_founder_who_has_one() -> None:
    data = mapped(venture("rec1", "Pair", people=["recFounderB", "recFounderA"]))

    assert data.items[0].year == "’24"


def test_a_venture_with_no_founder_has_no_year() -> None:
    data = mapped(venture("rec1", "Solo"))

    assert data.items[0].year == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [("’26", "26"), ("2026", "26"), ("'24", "24"), ("", ""), ("no digits", "")],
)
def test_year_slug_keeps_only_the_last_two_digits(value: str, expected: str) -> None:
    assert year_slug(value) == expected


def test_a_year_filter_narrows_the_list() -> None:
    data = mapped(
        venture("rec1", "Newer", people=["recFounderA"]),
        venture("rec2", "Older", people=["recFounderB"]),
    )

    result = select(data, years=["26"])

    assert [item.name for item in result.items] == ["Newer"]


def test_year_facets_are_newest_first() -> None:
    data = mapped(
        venture("rec1", "Newer", people=["recFounderA"]),
        venture("rec2", "Older", people=["recFounderB"]),
    )

    result = select(data)

    assert [(f.value, f.label, f.count) for f in result.years] == [
        ("26", "’26", 1),
        ("24", "’24", 1),
    ]


# --- the founders tab ---------------------------------------------------------
# Founders are `people` rows tagged `founder` AND ticked `onay`. The venture
# comes from the person's own `ventures` link — most founders have none, and
# gating on the link would have hidden the great majority of them.


def person(record_id: str, name: str, **fields: Any) -> AirtableRecord:
    """One approved `people` row tagged `founder`."""
    payload: dict[str, Any] = {"name": name, "tag": ["founder"], "onay": True}
    payload.update(fields)
    return AirtableRecord(id=record_id, fields=payload)


def with_people(
    *records: AirtableRecord, people_rows: list[AirtableRecord] | None = None
) -> VenturesData:
    return build(
        seeds.ventures(), list(records), sectors(), programs(), people_rows or [], {}
    )


def test_a_founder_with_no_venture_still_appears() -> None:
    data = with_people(people_rows=[person("recP1", "Oya Şahin", year="2025")])

    assert [c.name for c in data.founders] == ["Oya Şahin"]
    assert data.founders[0].venture == ""


def test_a_person_without_the_founder_tag_is_not_a_founder() -> None:
    rows = [
        person("recP1", "Kurucu"),
        AirtableRecord(id="recP2", fields={"name": "Fellow", "tag": ["fellow"], "onay": True}),
    ]

    data = with_people(people_rows=rows)

    assert [c.name for c in data.founders] == ["Kurucu"]


def test_a_founder_without_onay_is_not_published() -> None:
    rows = [
        person("recP1", "Onaylı"),
        AirtableRecord(id="recP2", fields={"name": "Taslak", "tag": ["founder"]}),
    ]

    data = with_people(people_rows=rows)

    assert [c.name for c in data.founders] == ["Onaylı"]


def test_the_venture_link_does_not_decide_who_is_a_founder() -> None:
    """The regression this tab was rebuilt for: reading founders off the venture
    link showed a fraction of the people who are actually founders."""
    rows = [person(f"recP{i}", f"Kurucu {i:02d}") for i in range(20)]
    rows[0] = person("recP0", "Kurucu 00", ventures=["rec1"])
    data = with_people(venture("rec1", "Tek", people=["recP0"]), people_rows=rows)

    assert len(data.founders) == 20
    assert sum(1 for c in data.founders if c.venture) == 1


def test_a_founder_carries_their_ventures_name_sectors_and_site() -> None:
    rows = [person("recP1", "Taha Yusuf Can", ventures=["rec1"])]
    data = with_people(
        venture("rec1", "ALGOFACT", sectors=[AI], websitesi="algofact.tech"),
        people_rows=rows,
    )

    card = data.founders[0]
    assert card.venture == "ALGOFACT"
    assert card.venture_slug == "algofact"
    assert card.website == "https://algofact.tech"
    assert card.sector_slugs == ["ai"]


def test_a_draft_venture_never_reaches_a_founder_card() -> None:
    rows = [person("recP1", "Kurucu", ventures=["rec1"])]
    draft = AirtableRecord(id="rec1", fields={"name": "Taslak", "websitesi": "x.com"})

    data = with_people(draft, people_rows=rows)

    assert data.founders[0].venture == ""
    assert data.founders[0].website == ""


def test_programmes_come_from_the_person_not_the_venture() -> None:
    rows = [person("recP1", "Kurucu", program=[TERRA], ventures=["rec1"])]
    data = with_people(venture("rec1", "Şirket", program=[ZEMIN]), people_rows=rows)

    assert data.founders[0].programs == ["Terra Future Labs"]


def test_a_founder_without_programmes_borrows_the_ventures() -> None:
    rows = [person("recP1", "Kurucu", ventures=["rec1"])]
    data = with_people(venture("rec1", "Şirket", program=[ZEMIN]), people_rows=rows)

    assert data.founders[0].programs == ["Zemin360"]


def test_founders_are_turkish_alphabetical() -> None:
    rows = [person("recP1", "Zeynep"), person("recP2", "Çağla"), person("recP3", "Ada")]

    data = with_people(people_rows=rows)

    assert [c.name for c in data.founders] == ["Ada", "Çağla", "Zeynep"]


def test_founders_sharing_a_name_get_distinct_slugs() -> None:
    rows = [person("recP1", "Kübra Nur Güven"), person("recP2", "Kübra Nur Güven")]

    data = with_people(people_rows=rows)

    assert [c.slug for c in data.founders] == ["kubra-nur-guven", "kubra-nur-guven-2"]


# --- the company under a founder's name ---------------------------------------


def test_the_published_venture_names_the_company() -> None:
    rows = [person("recP1", "Kurucu", organisation="Eski Ad", ventures=["rec1"])]
    data = with_people(venture("rec1", "ALGOFACT"), people_rows=rows)

    assert data.founders[0].venture == "ALGOFACT"


def test_organisation_names_it_when_there_is_no_venture() -> None:
    rows = [person("recP1", "Ataberk Özaydın", organisation="makromusic")]

    data = with_people(people_rows=rows)

    assert data.founders[0].venture == "makromusic"
    assert data.founders[0].venture_slug == ""
    assert data.founders[0].website == ""


def test_a_founder_with_neither_names_no_company() -> None:
    data = with_people(people_rows=[person("recP1", "Kurucu")])

    assert data.founders[0].venture == ""


def test_search_matches_the_organisation() -> None:
    data = with_people(people_rows=[person("recP1", "Kurucu", organisation="makromusic")])

    result = select(data, kind="founders", q="makro")

    assert [c.name for c in result.founders] == ["Kurucu"]


# --- which tab the page number walks ------------------------------------------


def two_tabs() -> VenturesData:
    rows = [person(f"recP{i}", f"Kurucu {i:02d}", year="2025") for i in range(30)]
    return with_people(
        *(venture(f"rec{i}", f"Venture {i:02d}") for i in range(5)), people_rows=rows
    )


def test_kind_ventures_pages_the_ventures() -> None:
    result = select(two_tabs(), kind="ventures", per_page=4)

    assert result.kind == "ventures"
    assert result.page.total == 5
    assert len(result.items) == 4
    assert result.founders == []


def test_kind_founders_pages_the_founders() -> None:
    result = select(two_tabs(), kind="founders", per_page=4)

    assert result.kind == "founders"
    assert result.page.total == 30
    assert len(result.founders) == 4
    assert result.items == []


def test_founder_pages_do_not_overlap_or_skip() -> None:
    data = two_tabs()

    seen = [
        c.slug
        for page in range(1, 4)
        for c in select(data, kind="founders", page=page, per_page=12).founders
    ]

    assert seen == [c.slug for c in data.founders]


# --- facets describe both tabs ------------------------------------------------


def test_a_programme_only_founders_carry_is_still_offered() -> None:
    rows = [person("recP1", "Kurucu", program=[TERRA])]
    data = with_people(venture("rec1", "Şirket", program=[ZEMIN]), people_rows=rows)

    result = select(data, kind="ventures")

    assert {f.value for f in result.programs} == {"zemin360", "terra-future-labs"}


def test_year_facets_include_founders_without_a_venture() -> None:
    data = with_people(people_rows=[person("recP1", "Kurucu", year="2021")])

    result = select(data)

    assert [(f.value, f.label) for f in result.years] == [("21", "’21")]


def test_a_founder_filter_narrows_the_founders_tab() -> None:
    rows = [
        person("recP1", "Eski", year="2021", program=[TERRA]),
        person("recP2", "Yeni", year="2026", program=[ZEMIN]),
    ]
    data = with_people(people_rows=rows)

    result = select(data, kind="founders", years=["26"])

    assert [c.name for c in result.founders] == ["Yeni"]


def test_search_on_the_founders_tab_matches_the_venture_name() -> None:
    rows = [person("recP1", "Kurucu", ventures=["rec1"])]
    data = with_people(venture("rec1", "Kybele"), people_rows=rows)

    result = select(data, kind="founders", q="kybele")

    assert [c.name for c in result.founders] == ["Kurucu"]


# --- logos editors get wrong --------------------------------------------------


def attachment(att_id: str, kind: str, name: str) -> dict[str, Any]:
    return {
        "id": att_id,
        "url": f"https://v5.airtableusercontent.com/{att_id}/full",
        "filename": name,
        "type": kind,
    }


def test_a_pdf_in_a_logo_column_is_not_offered_as_an_image() -> None:
    """One venture's `logo (renkli)` really is a PDF. An <img> pointed at it
    paints nothing, so the card would show an empty square."""
    data = mapped(
        venture(
            "rec1",
            "Şirket",
            **{"logo (renkli)": [attachment("attPdf", "application/pdf", "logo.pdf")]},
        )
    )

    assert data.items[0].logo == ""


def test_an_image_after_a_pdf_is_still_found() -> None:
    data = mapped(
        venture(
            "rec1",
            "Şirket",
            **{
                "logo (renkli)": [
                    attachment("attPdf", "application/pdf", "logo.pdf"),
                    attachment("attPng", "image/png", "logo.png"),
                ]
            },
        )
    )

    assert data.items[0].logo.endswith("attPng/full")


def test_the_two_logo_columns_stay_separate() -> None:
    data = mapped(
        venture(
            "rec1",
            "Şirket",
            **{
                "logo (renkli)": [attachment("attC", "image/jpeg", "colour.jpg")],
                "logo (beyaz)": [attachment("attW", "image/png", "white.png")],
            },
        )
    )

    assert data.items[0].logo.endswith("attC/full")
    assert data.items[0].logo_white.endswith("attW/full")


def test_a_pdf_logo_is_never_downloaded() -> None:
    records = [
        venture(
            "rec1",
            "Şirket",
            **{"logo (renkli)": [attachment("attPdf", "application/pdf", "logo.pdf")]},
        )
    ]

    assert media_refs(records, []) == []


def test_a_founders_linkedin_is_kept_for_the_card_link() -> None:
    rows = [person("recP1", "Kurucu", linkedin="linkedin.com/in/kurucu")]

    data = with_people(people_rows=rows)

    assert data.founders[0].linkedin == "https://linkedin.com/in/kurucu"


def test_a_javascript_linkedin_never_reaches_an_href() -> None:
    rows = [person("recP1", "Kurucu", linkedin="javascript:alert(1)")]

    data = with_people(people_rows=rows)

    assert data.founders[0].linkedin == ""
