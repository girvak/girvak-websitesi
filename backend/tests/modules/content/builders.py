"""
Module: tests/modules/content/builders.py
Layer: Test
Purpose: Build Airtable rows in the shape the real base uses, so a mapping test
         reads like the content it maps.

Dependencies: none
Called by: pytest
Calls: girvak/infra/airtable/client.py
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from girvak.infra.airtable.client import AirtableRecord
from girvak.modules.content.fragments import Fragments


def record(name: str, **fields: Any) -> AirtableRecord:
    """One fragment row.

    Args:
        name: The fragment name.
        **fields: Any other Airtable field, e.g. text or hover_text.

    Returns:
        A record the mapping can read.
    """
    payload: dict[str, Any] = {"name": name}
    for key, value in fields.items():
        payload[key.replace("_", " ") if key == "hover_text" else key] = value
    return AirtableRecord(id=f"rec{abs(hash(name)) % 10**8}", fields=payload)


def attachment(attachment_id: str, url: str, filename: str = "image.png") -> dict[str, Any]:
    """One attachment entry, without thumbnails.

    Args:
        attachment_id: Airtable's stable id.
        url: The (expiring) attachment URL.
        filename: Original filename.

    Returns:
        The attachment dict Airtable would return.
    """
    return {"id": attachment_id, "url": url, "filename": filename, "type": "image/png"}


def fragments(
    *records: AirtableRecord | Iterable[AirtableRecord],
    media: dict[str, str] | None = None,
) -> Fragments:
    """A table view over the given rows.

    Args:
        *records: The rows.
        media: Resolved attachment URLs, when the test cares about mirroring.

    Returns:
        The Fragments the mapping functions take.
    """
    flattened: list[AirtableRecord] = []
    for item in records:
        if isinstance(item, AirtableRecord):
            flattened.append(item)
        else:
            flattened.extend(item)
    return Fragments(flattened, media or {})
