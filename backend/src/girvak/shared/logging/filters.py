"""
Module: girvak/shared/logging/filters.py
Layer: Shared
Purpose: Two filters on the listener side of the queue — copy context onto the
         record, then mask secret-looking extras. Filters, not a formatter, so
         every handler is covered and a record can be dropped.

Dependencies: none
Called by: shared/logging/setup.py
Calls: shared/logging/context.py
"""

from __future__ import annotations

import logging

from girvak.shared.logging.context import request_id_var, user_id_var

REDACTED = "***"

# Substring match: a key like "airtable_api_key" must be caught too.
_SECRET_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "session",
    "otp",
    "private_key",
)

# Diagnostic keys that look sensitive but are not, plus the record attributes the
# formatter reads. Never redacted, never treated as extras.
_NEVER_REDACT = frozenset({"error_code", "status_code"})

_RESERVED_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
        "request_id",
        "user_id",
    }
)


class ContextFilter(logging.Filter):
    """Copy the request-scoped ids onto every record. Never drops a record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        return True


class RedactFilter(logging.Filter):
    """Mask extras whose key looks like a credential."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key in extra_keys(record):
            if key in _NEVER_REDACT:
                continue
            lowered = key.lower()
            if any(part in lowered for part in _SECRET_KEY_PARTS):
                setattr(record, key, REDACTED)
        return True


def extra_keys(record: logging.LogRecord) -> list[str]:
    """List the keys a call site passed through `extra=`.

    Args:
        record: The record being emitted.

    Returns:
        Custom attribute names, excluding stdlib record attributes.
    """
    return [
        key for key in vars(record) if key not in _RESERVED_RECORD_ATTRS and not key.startswith("_")
    ]
