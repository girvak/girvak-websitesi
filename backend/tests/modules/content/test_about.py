"""
Module: tests/modules/content/test_about.py
Layer: Test
Purpose: The about mapping: strips, their overlay rotation, and the hover copy
         split the design depends on.

Dependencies: none
Called by: pytest
Calls: girvak/modules/content/about.py
"""

from __future__ import annotations

from tests.modules.content.builders import fragments, record

from girvak.modules.content import about, seeds


def test_empty_table_keeps_the_seed() -> None:
    seed = seeds.about()

    assert about.build(seed, fragments()) == seed


def test_strips_take_their_headline_from_the_first_hover_line() -> None:
    rows = [
        record(
            "about_whatwesolve_1",
            text="yetenek",
            hover_text="Yetenek kaybı\nİlk satır açıklama.\nDevamı.",
        )
    ]

    strip = about.build(seeds.about(), fragments(*rows)).what_we_solve_strips[0]

    assert strip.label == "Yetenek"
    assert strip.headline == "Yetenek kaybı"
    assert strip.desc == "İlk satır açıklama. Devamı."


def test_strips_rotate_the_three_overlays() -> None:
    rows = [record(f"about_whatwesolve_{index}", text=f"s{index}") for index in range(1, 5)]

    strips = about.build(seeds.about(), fragments(*rows)).what_we_solve_strips

    assert strips[0].overlay_color == strips[3].overlay_color
    assert len({strip.overlay_color for strip in strips}) == 3


def test_story_paragraphs_keep_bold_as_strong() -> None:
    rows = [record("about_ourstory_text", text="Biz **2010** yılında kuruldunuz.")]

    paragraphs = about.build(seeds.about(), fragments(*rows)).story_paragraphs

    assert paragraphs == ["Biz <strong>2010</strong> yılında kuruldunuz."]


def test_cta_band_falls_back_to_the_seed_link() -> None:
    seed = seeds.about()
    rows = [record("about_reports_headline", text="Raporlar")]

    band = about.build(seed, fragments(*rows)).reports

    assert band.headline == "Raporlar"
    assert band.cta_href == seed.reports.cta_href


def test_section_heads_are_overridden_together() -> None:
    rows = [
        record("about_boardoftrustees_headline", text="Mütevelli Heyeti"),
        record("about_boardoftrustees_subheadline", text="Kurucular"),
    ]

    head = about.build(seeds.about(), fragments(*rows)).trustees

    assert (head.headline, head.subheadline) == ("Mütevelli Heyeti", "Kurucular")
