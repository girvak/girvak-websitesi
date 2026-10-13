"""
Module: girvak/modules/content/apply.py
Layer: Service
Purpose: Map the `applications` table onto the open calls on /apply.

         Like `ventures`, a record table rather than a fragment store: one row
         is one call — `headline`, `text`, `link`, `deadline` — and `onay` is
         the publish gate. A row without it is a draft and never renders.

         Open, closing soon or closed is left to the page. It depends on the
         day the visitor reads it, and a snapshot built yesterday must not keep
         a call open past its deadline. The base's own `Deadline Passed?`
         formula is ignored for the same reason. An empty deadline means the
         call is always open; one that cannot be read drops the row, so a typo
         never pins a call to the top as always open.

Dependencies: none
Called by: modules/content/service.py
Calls: modules/content/{fragments,schemas}.py
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from girvak.infra.airtable.client import AirtableRecord
from girvak.modules.content.fragments import field, link_of, text
from girvak.modules.content.schemas import ApplyContent, OpenCall
from girvak.shared.logging import LoggerName, get_logger

_logger = get_logger(LoggerName.SYSTEM)

_APPROVED_FIELDS = ("onay", "approved", "active")
_TITLE_FIELDS = ("headline", "name", "title")
_TEXT_FIELDS = ("text", "description")
_DEADLINE_FIELDS = ("deadline", "son başvuru", "due")


def build(records: Sequence[AirtableRecord]) -> ApplyContent:
    """Every approved call that has a title.

    Args:
        records: Rows of the Airtable `applications` table.

    Returns:
        The calls in Airtable order; the page sorts them for the day it is read.
    """
    calls: list[OpenCall] = []
    for record in records:
        fields = record.fields
        title = text(field(fields, *_TITLE_FIELDS))
        if field(fields, *_APPROVED_FIELDS) is not True or not title:
            continue
        raw = text(field(fields, *_DEADLINE_FIELDS))
        deadline = _deadline(raw)
        if raw and deadline is None:
            # An empty deadline means "always open", which pins the card first
            # in red. A deadline that cannot be read must not land there.
            _logger.warning("application_deadline_unreadable", extra={"record": record.id})
            continue
        calls.append(
            OpenCall(
                title=title,
                text=text(field(fields, *_TEXT_FIELDS)),
                href=link_of(fields),
                deadline=deadline,
            )
        )
    return ApplyContent(calls=calls)


def _deadline(raw: str) -> date | None:
    """The deadline as a date, or None when it is empty or unreadable.

    Airtable sends a date field as `2026-09-05`. A datetime column would send
    a full timestamp; its date part is what the card prints.
    """
    try:
        return date.fromisoformat(raw[:10]) if raw else None
    except ValueError:
        return None
