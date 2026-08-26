"""
Module: girvak/modules/content/fragments.py
Layer: Service
Purpose: Read the fragment store the way editors actually fill it: field names
         matched case-insensitively with aliases, families ordered by their
         trailing number, attachments resolved to mirrored URLs.
         Values in, values out — no I/O, no session.

Dependencies: none
Called by: modules/content/{home,about,fellow,people}.py, modules/content/service.py
Calls: infra/storage/media_mirror.py (pure helpers only)
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

from girvak.infra.airtable.client import AirtableRecord
from girvak.infra.storage.media_mirror import AttachmentRef, attachment_ref, cache_key

Fields = Mapping[str, Any]

# Variants: "full" (~3000px) for section imagery, "large" (~512px) for person
# cards — they render at 200-400px and would otherwise dominate page weight —
# and "orig" for logos, which must keep their alpha channel.
FULL = "full"
LARGE = "large"
ORIGINAL = "orig"

_ATTACHMENT_FIELDS = ("attachments", "attachment", "photo", "image")
_LOGO_FIELDS = ("positive_logo", "logo", "negative_logo")
_LINK_FIELDS = (
    "link",
    "url",
    "href",
    "external link",
    "external_link",
    "external link url",
)
_SAFE_HREF_SCHEMES = frozenset({"http", "https", "mailto", "tel"})


def field(fields: Fields, *names: str) -> Any:
    """First value among the given aliases, matched case-insensitively.

    Args:
        fields: One Airtable row's fields.
        *names: Field names to try, in order.

    Returns:
        The value, or None when the row has none of them.
    """
    lowered = {key.lower(): value for key, value in fields.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def text(value: Any) -> str:
    """Trim an Airtable text value to a clean string.

    Args:
        value: Raw field value.

    Returns:
        The trimmed string, empty when the value is missing.
    """
    return "" if value is None else str(value).strip()


def tags(fields: Fields) -> list[str]:
    """Tags of a row, whether Airtable stored one value or a list.

    Args:
        fields: One row's fields.

    Returns:
        Tag strings in row order.
    """
    value = field(fields, "tag", "tags")
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)] if value else []


def trailing_number(name: str) -> int:
    """Ordering key of a fragment name: `index_impact_5` sorts as 5.

    Args:
        name: Fragment name.

    Returns:
        The trailing integer, or 0 when the name has none.
    """
    match = re.search(r"(\d+)\s*$", name or "")
    return int(match.group(1)) if match else 0


def safe_href(url: str, fallback: str = "#") -> str:
    """Reject a link an editor should not be able to inject.

    A fragment's link lands in an href, so `javascript:` and `data:` are dropped
    rather than rendered.

    Args:
        url: Raw value from Airtable.
        fallback: Returned when the value is empty or unsafe.

    Returns:
        A safe href.
    """
    candidate = (url or "").strip()
    if not candidate:
        return fallback
    if candidate.startswith(("#", "/")):
        return candidate
    if urlparse(candidate).scheme.lower() in _SAFE_HREF_SCHEMES:
        return candidate
    return fallback


def link_of(fields: Fields, fallback: str = "#") -> str:
    """Link of a row, from whichever URL field the editor used.

    Args:
        fields: One row's fields.
        fallback: Returned when no usable link is present.

    Returns:
        A safe href.
    """
    return safe_href(text(field(fields, *_LINK_FIELDS)), fallback)


def paragraphs(value: str) -> list[str]:
    """Split a multi-line text field into non-empty lines.

    Args:
        value: Raw text.

    Returns:
        Trimmed lines, blanks dropped.
    """
    lines = [line.strip() for line in value.replace("\r\n", "\n").split("\n")]
    return [line for line in lines if line]


class Fragments:
    """One Airtable table, indexed the way the mapping needs it."""

    def __init__(self, records: Sequence[AirtableRecord], media: Mapping[str, str]) -> None:
        self._init_rows([record.fields for record in records], media)

    def _init_rows(self, rows: list[Fields], media: Mapping[str, str]) -> None:
        self._rows = rows
        self._by_name = {text(field(row, "name")): row for row in rows if text(field(row, "name"))}
        self._media = media

    def where(self, keep: Callable[[Fields], bool]) -> Fragments:
        """A view of this table holding only the rows a predicate keeps.

        Used where a table carries its own visibility column — the `fellow`
        table's `active` box, for one — so that rule stays with the page that
        owns it instead of leaking into the fetch layer.

        Args:
            keep: Predicate over a row's fields.

        Returns:
            A new Fragments over the kept rows, sharing this media map.
        """
        view = Fragments.__new__(Fragments)
        view._init_rows([row for row in self._rows if keep(row)], self._media)
        return view

    def __bool__(self) -> bool:
        return bool(self._rows)

    @property
    def rows(self) -> list[Fields]:
        """Every row of the table, in Airtable order."""
        return self._rows

    def row(self, name: str) -> Fields:
        """Row with this fragment name.

        Args:
            name: Fragment name.

        Returns:
            Its fields, or an empty mapping when absent.
        """
        return self._by_name.get(name, {})

    def text_of(self, name: str) -> str:
        """`text` field of one fragment.

        Args:
            name: Fragment name.

        Returns:
            The trimmed text, empty when the fragment or field is missing.
        """
        return text(field(self.row(name), "text"))

    def hover_of(self, name: str) -> str:
        """`hover text` field of one fragment.

        Args:
            name: Fragment name.

        Returns:
            The trimmed hover text, empty when missing.
        """
        return text(field(self.row(name), "hover text", "hover_text"))

    def family(self, prefix: str) -> list[Fields]:
        """Rows whose name starts with a prefix, ordered by trailing number.

        Args:
            prefix: Name prefix, e.g. `index_impact_`.

        Returns:
            Matching rows in numeric order.
        """
        rows = [row for row in self._rows if text(field(row, "name")).startswith(prefix)]
        return sorted(rows, key=lambda row: trailing_number(text(field(row, "name"))))

    def numbered(self, prefix: str) -> list[Fields]:
        """Rows named exactly `<prefix><number>`, ordered by that number.

        Excludes `<prefix>headline` and other named siblings.

        Args:
            prefix: Name prefix, e.g. `about_whatwesolve_`.

        Returns:
            Matching rows in numeric order.
        """
        pattern = re.compile(re.escape(prefix) + r"\d+\s*$")
        rows = [row for row in self._rows if pattern.match(text(field(row, "name")))]
        return sorted(rows, key=lambda row: trailing_number(text(field(row, "name"))))

    def with_tag(self, tag: str) -> list[Fields]:
        """Rows carrying one tag.

        Args:
            tag: Tag to match, case-insensitively.

        Returns:
            Matching rows in Airtable order.
        """
        wanted = tag.lower()
        return [row for row in self._rows if any(item.lower() == wanted for item in tags(row))]

    def image(self, fields: Fields, variant: str = FULL, *names: str) -> str:
        """First attachment of a row as a URL.

        Args:
            fields: One row's fields.
            variant: FULL, LARGE, or ORIGINAL.
            *names: Attachment field aliases; defaults cover the base's naming.

        Returns:
            The mirrored URL, the expiring Airtable URL when the mirror has no
            copy, or an empty string when the row has no attachment.
        """
        urls = self.images(fields, variant, *names)
        return urls[0] if urls else ""

    def images(self, fields: Fields, variant: str = FULL, *names: str) -> list[str]:
        """Every attachment of a row as URLs, in order.

        Args:
            fields: One row's fields.
            variant: FULL, LARGE, or ORIGINAL.
            *names: Attachment field aliases; defaults cover the base's naming.

        Returns:
            URLs in Airtable order.
        """
        value = field(fields, *(names or _ATTACHMENT_FIELDS))
        if not isinstance(value, list):
            return []

        urls: list[str] = []
        for attachment in value:
            if not isinstance(attachment, dict):
                continue
            ref = attachment_ref(attachment, variant)
            if ref is None:
                continue
            urls.append(
                self._media.get(cache_key(ref.attachment_id, ref.requested), ref.remote_url)
            )
        return [url for url in urls if url]

    def logo(self, fields: Fields) -> str:
        """Partner logo URL, always the original so alpha survives.

        Args:
            fields: One partner row's fields.

        Returns:
            The logo URL, empty when the row has none.
        """
        return self.image(fields, ORIGINAL, *_LOGO_FIELDS)


def collect_refs(
    records: Sequence[AirtableRecord], variant: str, *names: str
) -> list[AttachmentRef]:
    """Every attachment reference a mapping pass will ask for.

    The mirror downloads these before mapping runs, so the mapping itself stays
    free of I/O.

    Args:
        records: Rows of one table.
        variant: Which rendition that table's images are used at.
        *names: Attachment field aliases; defaults cover the base's naming.

    Returns:
        One reference per attachment, in row order.
    """
    refs: list[AttachmentRef] = []
    for record in records:
        value = field(record.fields, *(names or _ATTACHMENT_FIELDS))
        if not isinstance(value, list):
            continue
        for attachment in value:
            if isinstance(attachment, dict):
                ref = attachment_ref(attachment, variant)
                if ref is not None:
                    refs.append(ref)
    return refs


def logo_refs(records: Sequence[AirtableRecord]) -> list[AttachmentRef]:
    """Attachment references for partner logo fields.

    Args:
        records: Rows of the partner table.

    Returns:
        One reference per logo attachment.
    """
    return collect_refs(records, ORIGINAL, *_LOGO_FIELDS)
