"""
Module: girvak/shared/logging/formatter.py
Layer: Shared
Purpose: Serialize a record as one line of JSON with stable keys.
         Serialisation only — it adds no field and masks no value.

Dependencies: none
Called by: shared/logging/setup.py
Calls: shared/logging/filters.py (extra_keys)
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from girvak.shared.logging.filters import extra_keys


class JsonFormatter(logging.Formatter):
    """One JSON object per line, UTF-8, keys in a fixed order."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
        }

        for key in extra_keys(record):
            payload[key] = _jsonable(getattr(record, key))

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def _jsonable(value: object) -> object:
    if isinstance(value, str | int | float | bool | type(None) | list | dict):
        return value
    return str(value)
