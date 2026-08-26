"""
Module: girvak/shared/logging/context.py
Layer: Shared
Purpose: Request-scoped values every log line carries. Bound at the edge
         (http/middleware), read by the context filter, reset in a finally.

Dependencies: none
Called by: http/middleware/request_id.py, shared/logging/filters.py
Calls: nothing
"""

from __future__ import annotations

from contextvars import ContextVar, Token

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def bind_request_id(request_id: str) -> Token[str | None]:
    """Bind the correlation id for this request.

    Args:
        request_id: Value echoed to the client as X-Request-ID.

    Returns:
        The token the caller must pass to reset_request_id in a finally block.
    """
    return request_id_var.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the previous correlation id.

    Args:
        token: The token bind_request_id returned.
    """
    request_id_var.reset(token)
