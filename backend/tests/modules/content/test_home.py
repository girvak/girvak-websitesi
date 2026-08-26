"""
Module: tests/modules/content/test_home.py
Layer: Test
Purpose: The home mapping: what Airtable overrides, what the seed keeps, and the
         shapes the design depends on (3x3 impact grid, split headlines).

Dependencies: none
Called by: pytest
Calls: girvak/modules/content/home.py
"""

from __future__ import annotations

from tests.modules.content.builders import attachment, fragments, record

from girvak.modules.content import home, seeds


def test_missing_fragments_keep_the_seed() -> None:
    seed = seeds.home()

    content = home.build(seed, fragments(), fragments())

    assert content.seo.title == seed.seo.title
    assert content.impact == seed.impact
    assert content.what_we_do == seed.what_we_do
    assert content.footer == seed.footer


def test_seo_is_overridden_when_airtable_has_it() -> None:
    content = home.build(
        seeds.home(),
        fragments(
            record("index_seo_title", text="GİRVAK"),
            record("index_seo_description", text="Girişimcilik Vakfı"),
        ),
        fragments(),
    )

    assert content.seo.title == "GİRVAK"
    assert content.seo.description == "Girişimcilik Vakfı"


def test_impact_rows_fill_the_grid_left_to_right() -> None:
    rows = [
        record(f"index_impact_{index}", text=f"{index}00+ label {index}", hover_text=f"d{index}")
        for index in range(1, 5)
    ]

    content = home.build(seeds.home(), fragments(*rows), fragments())

    positions = [(tile.row, tile.col) for tile in content.impact]
    assert positions == [(1, 1), (1, 2), (1, 3), (2, 1)]
    assert content.impact[0].suffix == "+"
    assert content.impact[0].label == "label 1"
    assert content.impact[0].desc == "d1"


def test_impact_image_row_is_not_a_tile() -> None:
    rows = [
        record("index_impact_1", text="120+ fellows"),
        record("index_impact_image", attachments=[attachment("att1", "https://x/y.png")]),
    ]

    content = home.build(seeds.home(), fragments(*rows), fragments())

    assert len(content.impact) == 1
    assert content.impact[0].row == 1


def test_impact_image_uses_the_mirrored_url() -> None:
    media = {"att1:full": "/media/att1_full.png"}
    rows = [record("index_impact_image", attachments=[attachment("att1", "https://x/y.png")])]

    content = home.build(seeds.home(), fragments(*rows, media=media), fragments())

    assert content.impact_image == "/media/att1_full.png"


def test_unmirrored_attachment_falls_back_to_the_airtable_url() -> None:
    rows = [record("index_impact_image", attachments=[attachment("att1", "https://x/y.png")])]

    content = home.build(seeds.home(), fragments(*rows), fragments())

    assert content.impact_image == "https://x/y.png"


def test_what_we_do_card_splits_lead_and_eyebrow() -> None:
    row = record(
        "index_whatwedo_1",
        text="We back potential. That's the Fellow Program.",
        hover_text="Back of the card.",
    )

    content = home.build(seeds.home(), fragments(row), fragments())

    card = content.what_we_do[0]
    assert card.lead == "We back potential."
    assert card.sub == "That's the Fellow Program."
    assert card.eyebrow == "Fellow Program"
    assert card.text == "Back of the card."


def test_partners_headline_splits_on_the_last_comma() -> None:
    content = home.build(
        seeds.home(),
        fragments(record("index_partners_headline", text="Bir arada, daha güçlü")),
        fragments(),
    )

    assert content.partners.headline_pre == "Bir arada, "
    assert content.partners.headline_highlight == "daha güçlü"


def test_only_approved_partners_are_published() -> None:
    partners = fragments(
        record("a", organization="Approved", onay=True, logo=[attachment("l1", "https://x/a.png")]),
        record("b", organization="Pending", logo=[attachment("l2", "https://x/b.png")]),
    )

    content = home.build(seeds.home(), fragments(), partners)

    assert [partner.name for partner in content.partners.logos] == ["Approved"]


def test_main_tagged_partner_becomes_the_featured_logo() -> None:
    partners = fragments(
        record(
            "a",
            organization="Main Sponsor",
            onay=True,
            tags=["main"],
            logo=[attachment("l1", "https://x/a.png")],
        ),
        record("b", organization="Other", onay=True, logo=[attachment("l2", "https://x/b.png")]),
    )

    content = home.build(seeds.home(), fragments(), partners)

    assert content.partners.featured.name == "Main Sponsor"
    assert [partner.name for partner in content.partners.logos] == ["Other"]


def test_footer_explore_links_follow_their_numbers() -> None:
    rows = [
        record("index_footer_explore_2", text="About", link="/about"),
        record("index_footer_explore_1", text="Home", link="/"),
    ]

    content = home.build(seeds.home(), fragments(*rows), fragments())

    assert [link.label for link in content.footer.explore_links] == ["Home", "About"]


def test_unsafe_link_is_replaced_with_the_fallback() -> None:
    row = record("index_footer_explore_1", text="Bad", link="javascript:alert(1)")

    content = home.build(seeds.home(), fragments(row), fragments())

    assert content.footer.explore_links[0].href == "#"


def test_hero_subheadline_marks_the_highlight() -> None:
    row = record("index_hero_subheadline", text="Girişimcilik **bir bakış açısıdır.** Devamı.")

    content = home.build(seeds.home(), fragments(row), fragments())

    assert content.hero.subhead_pre == "Girişimcilik "
    assert content.hero.subhead_highlight == "bir bakış açısıdır."
    assert content.hero.subhead_post == " Devamı."


def test_hero_ctas_render_secondary_first() -> None:
    rows = [
        record("index_hero_cta_primary", text="Başvur", link="/apply"),
        record("index_hero_cta_secondary", text="Keşfet", link="/discover"),
    ]

    content = home.build(seeds.home(), fragments(*rows), fragments())

    assert [cta.label for cta in content.hero.ctas] == ["Keşfet", "Başvur"]
    assert content.hero.ctas[0].href == "/discover"
