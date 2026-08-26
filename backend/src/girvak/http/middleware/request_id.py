"""
Module: girvak/http/middleware/request_id.py
Layer: Router
Purpose: Give every request a correlation id, bind it on the log context, and
         echo it on every response. Support asks for this header, not for a
         message.

Dependencies: none
Called by: main.py (middleware stack, outermost application middleware)
Calls: shared/logging/context.py
"""

from __future__ import annotations

import uuid

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from girvak.shared.logging import bind_request_id, reset_request_id

HEADER = "x-request-id"

# A client-supplied id reaches logs and response headers, so it is length-capped
# and stripped of anything that is not id-shaped.
_MAX_LENGTH = 64
_ALLOWED = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


class RequestIdMiddleware:
    """Bind the request id for the duration of the request, then reset it."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the request with a bound correlation id.

        Args:
            scope: ASGI scope.
            receive: ASGI receive channel.
            send: ASGI send channel.
        """
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = _incoming_or_new(Headers(scope=scope))
        token = bind_request_id(request_id)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                headers.append((HEADER.encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self._app(scope, receive, send_with_header)
        finally:
            reset_request_id(token)


def _incoming_or_new(headers: Headers) -> str:
    cleaned = "".join(char for char in headers.get(HEADER, "") if char in _ALLOWED)
    return cleaned[:_MAX_LENGTH] or uuid.uuid4().hex
