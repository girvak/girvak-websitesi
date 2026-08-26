"""
Module: girvak/infra/airtable/client.py
Layer: Repository
Purpose: Read rows out of the Airtable content base. Knows pagination, auth,
         and timeouts; knows nothing about what a row means.

Dependencies:
    - Settings: token, base id, timeouts, connection cap

Called by: modules/content/service.py
Calls: nothing
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from girvak.config import Settings
from girvak.shared.errors import ServiceUnavailableError
from girvak.shared.logging import LoggerName, get_logger

_API_ROOT = "https://api.airtable.com/v0"
_PAGE_SIZE = 100
# A content table with more pages than this is a base someone should split; the
# bound exists so a pagination bug cannot loop forever.
_MAX_PAGES = 50

_logger = get_logger(LoggerName.SYSTEM)


@dataclass(frozen=True)
class AirtableRecord:
    """One row: its id and its fields, exactly as Airtable returned them."""

    id: str
    fields: Mapping[str, Any]


class AirtableClient:
    """HTTP access to one Airtable base."""

    def __init__(self, settings: Settings) -> None:
        airtable = settings.airtable
        if not (airtable.api_key and airtable.base_id):
            raise ValueError("AirtableClient needs AIRTABLE__API_KEY and AIRTABLE__BASE_ID")

        self._base_id = airtable.base_id
        self._client = httpx.AsyncClient(
            base_url=_API_ROOT,
            headers={"Authorization": f"Bearer {airtable.api_key.get_secret_value()}"},
            timeout=httpx.Timeout(
                airtable.total_timeout_seconds,
                connect=airtable.connect_timeout_seconds,
            ),
            limits=httpx.Limits(max_connections=airtable.max_connections),
        )

    async def list_records(self, table: str) -> list[AirtableRecord]:
        """Fetch every row of one table.

        Args:
            table: Table name as it appears in the base.

        Returns:
            Rows in Airtable's own order.

        Raises:
            ServiceUnavailableError: Airtable refused, timed out, or answered
                with something that is not a record page.
        """
        path = f"/{self._base_id}/{quote(table, safe='')}"
        records: list[AirtableRecord] = []
        offset: str | None = None

        for _ in range(_MAX_PAGES):
            params: dict[str, Any] = {"pageSize": _PAGE_SIZE}
            if offset:
                params["offset"] = offset

            try:
                response = await self._client.get(path, params=params)
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPError as exc:
                # The URL carries the base id but never the token (it is a header).
                raise ServiceUnavailableError(
                    "İçerik kaynağına şu anda ulaşılamıyor.",
                    {"table": table},
                ) from exc

            for raw in payload.get("records", []):
                record_id = str(raw.get("id") or "")
                fields = raw.get("fields") or {}
                if record_id and isinstance(fields, dict):
                    records.append(AirtableRecord(id=record_id, fields=fields))

            offset = payload.get("offset")
            if not offset:
                return records

        _logger.warning("airtable_pagination_capped", extra={"table": table, "pages": _MAX_PAGES})
        return records

    async def aclose(self) -> None:
        """Close the connection pool."""
        await self._client.aclose()


_client: AirtableClient | None = None


def init_client(settings: Settings) -> None:
    """Open the process-wide Airtable client, when Airtable is the source.

    Args:
        settings: Decides whether Airtable is used at all.
    """
    global _client
    if _client is not None or settings.content.source != "airtable":
        return
    _client = AirtableClient(settings)


async def dispose_client() -> None:
    """Close the client on process shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


def client() -> AirtableClient | None:
    """Return the process client.

    Returns:
        The client, or None when this deployment reads the committed seed only.
    """
    return _client
