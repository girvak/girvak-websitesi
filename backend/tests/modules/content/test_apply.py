"""
Module: tests/modules/content/test_apply.py
Layer: Test
Purpose: The open calls on /apply: only approved rows render, links are made
         safe, and a deadline arrives as a date — or as none, for a call that is
         always open.

Dependencies: none
Called by: pytest
Calls: girvak/modules/content/apply.py
"""

from __future__ import annotations

from datetime import date
from typing import Any

from girvak.infra.airtable.client import AirtableRecord
from girvak.modules.content import apply


def row(headline: str, **fields: Any) -> AirtableRecord:
    """One `applications` row, approved unless the test says otherwise."""
    payload: dict[str, Any] = {"headline": headline, "onay": True, **fields}
    return AirtableRecord(id=f"rec{abs(hash(headline)) % 10**8}", fields=payload)


def test_a_call_carries_what_its_card_prints() -> None:
    content = apply.build(
        [
            row(
                "Airpreneurs",
                text="Shape the future of aviation.",
                link="https://example.org/form",
                deadline="2026-09-20",
            )
        ]
    )

    [call] = content.calls
    assert call.title == "Airpreneurs"
    assert call.text == "Shape the future of aviation."
    assert call.href == "https://example.org/form"
    assert call.deadline == date(2026, 9, 20)


def test_a_row_without_onay_is_a_draft() -> None:
    content = apply.build([row("Taslak", onay=False), AirtableRecord("recX", {"headline": "Yok"})])

    assert content.calls == []


def test_a_call_without_a_deadline_is_always_open() -> None:
    [call] = apply.build([row("Fellow Program")]).calls

    assert call.deadline is None


def test_an_unreadable_deadline_drops_the_row_rather_than_pinning_it_open() -> None:
    content = apply.build(
        [row("Bozuk", deadline="next week"), row("Sağlam", deadline="2026-09-05")]
    )

    assert [call.title for call in content.calls] == ["Sağlam"]


def test_a_datetime_deadline_keeps_its_date() -> None:
    [call] = apply.build([row("Saatli", deadline="2026-09-05T00:00:00.000Z")]).calls

    assert call.deadline == date(2026, 9, 5)


def test_an_unsafe_link_is_dropped() -> None:
    [call] = apply.build([row("Kötü", link="javascript:alert(1)")]).calls

    assert call.href == "#"


def test_a_row_without_a_headline_is_skipped_and_order_is_kept() -> None:
    content = apply.build([row("B"), row(""), row("A")])

    assert [call.title for call in content.calls] == ["B", "A"]


def test_a_ticked_popup_is_carried_and_an_unticked_one_is_not() -> None:
    # Airtable leaves an unticked checkbox out of the row entirely.
    content = apply.build([row("Fellow Program", popup=True), row("Airpreneurs")])

    assert [call.popup for call in content.calls] == [True, False]
