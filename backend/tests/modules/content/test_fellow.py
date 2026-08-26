"""
Module: tests/modules/content/test_fellow.py
Layer: Test
Purpose: The fellow-program mapping, including the two rules that bite: the
         `active` visibility box and the several spellings of the challenger
         "what you'll do" family.

Dependencies: none
Called by: pytest
Calls: girvak/modules/content/fellow.py
"""

from __future__ import annotations

from tests.modules.content.builders import attachment, fragments, record

from girvak.modules.content import fellow, seeds


def test_empty_table_keeps_the_seed() -> None:
    seed = seeds.fellow()

    assert fellow.build(seed, fragments()) == seed


def test_when_any_row_is_active_the_others_are_ignored() -> None:
    table = fragments(
        record("fellow_hero_headline", text="Aktif başlık", active=True),
        record("fellow_fellows_headline", text="Pasif başlık"),
    )

    content = fellow.build(seeds.fellow(), table)

    assert content.hero_headline == "Aktif başlık"
    assert content.fellows_headline == seeds.fellow().fellows_headline


def test_without_any_active_box_every_row_counts() -> None:
    table = fragments(
        record("fellow_hero_headline", text="Başlık"),
        record("fellow_fellows_headline", text="Fellowlar"),
    )

    content = fellow.build(seeds.fellow(), table)

    assert content.hero_headline == "Başlık"
    assert content.fellows_headline == "Fellowlar"


def test_hero_headline_breaks_after_the_first_sentence() -> None:
    table = fragments(record("fellow_hero_headline", text="A community that backs you. For life."))

    html = fellow.build(seeds.fellow(), table).hero_headline_html

    assert html == 'A community that backs you.<br /><span class="hl">For life.</span>'


def test_editor_markup_is_escaped_not_rendered() -> None:
    table = fragments(record("fellow_about_text", text="<script>alert(1)</script> **vurgu**"))

    html = fellow.build(seeds.fellow(), table).about_html

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert '<span class="hl">vurgu</span>' in html


def test_how_block_last_line_becomes_the_kicker() -> None:
    table = fragments(
        record("fellow_application_1_subheadline", text="Kimler başvurabilir"),
        record("fellow_application_1_text", text="Birinci satır\nİkinci satır\nThat's it."),
    )

    block = fellow.build(seeds.fellow(), table).application

    assert block.label == "Kimler başvurabilir"
    assert block.kicker == "That's it."
    assert len(block.paragraphs) == 2


def test_expect_cards_alternate_their_corner_cut() -> None:
    rows = [
        record(
            f"fellow_whattoexpect_{index}",
            tag="fellow_whattoexpect",
            text=f"**Kart {index}**\nAçıklama",
        )
        for index in range(1, 4)
    ]

    cards = fellow.build(seeds.fellow(), fragments(*rows)).what_to_expect

    assert [card.name for card in cards] == ["Kart 1", "Kart 2", "Kart 3"]
    assert cards[0].cap == cards[2].cap
    assert cards[0].cap != cards[1].cap


def test_challenger_items_are_found_whatever_the_apostrophe() -> None:
    rows = [
        record("challenger_whatyoulldo_2", text="İkinci"),
        record("challenger_whatyou'lldo_1", text="Birinci"),
    ]

    items = fellow.build(seeds.fellow(), fragments(*rows)).what_youll_do

    assert [item.text for item in items] == ["Birinci", "İkinci"]


def test_challenger_item_without_an_image_uses_the_shipped_icon() -> None:
    rows = [record("challenger_whatyoulldo_1", text="Birinci")]

    items = fellow.build(seeds.fellow(), fragments(*rows)).what_youll_do

    assert items[0].image.startswith("/images/chal-")


def test_challenger_item_image_uses_the_mirrored_url() -> None:
    media = {"attX:full": "/media/attX_full.png"}
    rows = [
        record(
            "challenger_whatyoulldo_1",
            text="Birinci",
            attachments=[attachment("attX", "https://x/i.png")],
        )
    ]

    items = fellow.build(seeds.fellow(), fragments(*rows, media=media)).what_youll_do

    assert items[0].image == "/media/attX_full.png"
