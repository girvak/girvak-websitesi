"""
Module: girvak/http/middleware/security_headers.py
Layer: Router
Purpose: Response headers that hold for every route: no MIME sniffing, no
         framing, a referrer policy, and no access to camera/microphone/location.

Dependencies: none
Called by: main.py (middleware stack)
Calls: nothing
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
)


class SecurityHeadersMiddleware:
    """Add the fixed security headers to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Append the headers as the response starts.

        Args:
            scope: ASGI scope.
            receive: ASGI receive channel.
            send: ASGI send channel.
        """
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers.extend((name, value) for name, value in _HEADERS if name not in present)
                message["headers"] = headers
            await send(message)

        await self._app(scope, receive, send_with_headers)
