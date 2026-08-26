"""
Module: tests/modules/content/test_people.py
Layer: Test
Purpose: Grouping, ordering, and the fields the person cards read. Ordering is
         Turkish alphabetical, which no default locale gives you.

Dependencies: none
Called by: pytest
Calls: girvak/modules/content/people.py
"""

from __future__ import annotations

from tests.modules.content.builders import attachment, fragments, record

from girvak.modules.content import people


def test_rows_are_grouped_by_their_tag() -> None:
    table = fragments(
        record("Ayşe Yılmaz", tag=["mh"]),
        record("Mehmet Demir", tag=["yk"]),
        record("Zeynep Kaya", tag=["team"]),
        record("Ali Veli", tag=["fellow"]),
    )

    content = people.build(table)

    assert [person.first for person in content.trustees] == ["Ayşe"]
    assert [person.first for person in content.directors] == ["Mehmet"]
    assert [person.first for person in content.team] == ["Zeynep"]
    assert [person.first for person in content.fellows] == ["Ali"]


def test_misspelled_challenger_tags_still_group() -> None:
    table = fragments(
        record("Bir Kişi", tag=["challlenger"]),
        record("İki Kişi", tag=["challengers"]),
    )

    content = people.build(table)

    assert len(content.challengers) == 2


def test_names_sort_in_turkish_alphabetical_order() -> None:
    table = fragments(
        record("Zeynep Ak", tag=["mh"]),
        record("Şule Ak", tag=["mh"]),
        record("Irmak Ak", tag=["mh"]),
        record("İnci Ak", tag=["mh"]),
    )

    content = people.build(table)

    # Turkish order: ı < i < ş < z. ASCII order would put Ş after Z.
    assert [person.first for person in content.trustees] == ["Irmak", "İnci", "Şule", "Zeynep"]


def test_board_opens_with_the_chair_and_vice_chair() -> None:
    table = fragments(
        record("Ahmet Öz", tag=["yk"]),
        record("Yomi Kastro", tag=["yk"]),
        record("Sina Afra", tag=["yk"]),
    )

    content = people.build(table)

    assert [person.first for person in content.directors] == ["Sina", "Yomi", "Ahmet"]


def test_last_word_of_the_name_is_the_surname() -> None:
    table = fragments(record("Deniz Hale Durakbaşı", tag=["team"]))

    person = people.build(table).team[0]

    assert (person.first, person.last) == ("Deniz Hale", "Durakbaşı")


def test_person_photo_uses_the_large_rendition() -> None:
    media = {"att9:large": "/media/att9_large.png"}
    table = fragments(
        record("Bir Kişi", tag=["team"], photo=[attachment("att9", "https://x/p.png")]),
        media=media,
    )

    assert people.build(table).team[0].photo == "/media/att9_large.png"


def test_year_comes_from_a_field_or_from_the_tag() -> None:
    table = fragments(
        record("Alan Kişi", tag=["fellow"], year="2021"),
        record("Baska Kisi", tag=["fellow_22", "fellow"]),
    )

    content = people.build(table)
    years = {person.first: person.year for person in content.fellows}

    assert years["Alan"] == "’21"
    assert years["Baska"] == "’22"


def test_a_profile_url_without_a_scheme_is_completed() -> None:
    table = fragments(record("Ali Veli", tag=["team"], linkedin="linkedin.com/in/someone"))

    assert people.build(table).team[0].linkedin == "https://linkedin.com/in/someone"


def test_a_bare_linkedin_link_is_dropped() -> None:
    table = fragments(record("Ali Veli", tag=["team"], linkedin="https://linkedin.com"))

    assert people.build(table).team[0].linkedin == ""


def test_rows_without_a_name_are_skipped() -> None:
    table = fragments(record("", tag=["team"]), record("Gerçek Kişi", tag=["team"]))

    assert len(people.build(table).team) == 1


def test_spotlight_never_exceeds_the_pool() -> None:
    table = fragments(
        record(f"Kisi {index}", tag=["fellow"], photo=[attachment(f"a{index}", "https://x/p.png")])
        for index in range(3)
    )
    pool = people.fellow_pool(table)

    picked = people.spotlight(pool, 8)

    assert len(picked) == 3
    assert {fellow.color for fellow in picked} <= {"teal", "coral", "ink"}


def test_fellow_pool_skips_anyone_without_a_photo() -> None:
    table = fragments(
        record("Fotolu Kisi", tag=["fellow"], photo=[attachment("a1", "https://x/p.png")]),
        record("Fotosuz Kisi", tag=["fellow"]),
    )

    pool = people.fellow_pool(table)

    assert [fellow.name for fellow in pool] == ["Fotolu Kisi"]
