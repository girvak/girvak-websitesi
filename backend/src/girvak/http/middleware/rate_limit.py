"""
Module: girvak/http/middleware/rate_limit.py
Layer: Router
Purpose: Cap how often one client may call a write surface. Transport policy:
         which URL, which window, which cap — never a product rule.

Dependencies:
    - Settings: every cap and window

Called by: main.py (middleware stack)
Calls: shared/errors/
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from girvak.config import Settings
from girvak.shared.errors import RateLimitError

# Bound on distinct client keys held in memory. Above it the oldest bucket is
# dropped: a limiter that grows without a ceiling is the leak it was meant to stop.
_MAX_TRACKED_KEYS = 10_000


@dataclass(frozen=True)
class Rule:
    """One capped surface."""

    method: str
    path: str
    limit: int
    window_seconds: int


class RateLimitMiddleware:
    """In-process sliding-window limiter.

    Counters live in this process. That is honest for a single API container and
    is the reason `infra/cache/` is not involved: a shared counter is a Redis
    dependency, and nothing here needs one yet. Running more than one replica
    means the effective cap is per replica — move the counter to Redis then.
    """

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self._app = app
        self._rules = (
            Rule(
                method="POST",
                path="/v1/newsletter",
                limit=settings.limits.newsletter_per_ip_per_hour,
                window_seconds=3600,
            ),
            Rule(
                method="POST",
                path="/v1/content/refresh",
                limit=settings.limits.refresh_per_minute,
                window_seconds=60,
            ),
        )
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Reject the request when its client is over the cap for that URL.

        Args:
            scope: ASGI scope.
            receive: ASGI receive channel.
            send: ASGI send channel.
        """
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope)
        rule = self._match(request)
        if rule is None:
            await self._app(scope, receive, send)
            return

        client = request.client.host if request.client else "unknown"
        retry_after = self._register(rule, client)
        if retry_after is not None:
            error = RateLimitError(
                "Çok fazla istek gönderildi. Lütfen biraz sonra tekrar deneyin.",
                retry_after_seconds=retry_after,
            )
            response = JSONResponse(
                status_code=error.http_status_code,
                content={
                    "error_code": error.error_code,
                    "message": error.message,
                    "details": {},
                },
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return

        await self._app(scope, receive, send)

    def _match(self, request: Request) -> Rule | None:
        for rule in self._rules:
            if request.method == rule.method and request.url.path.rstrip("/") == rule.path:
                return rule
        return None

    def _register(self, rule: Rule, client: str) -> int | None:
        """Record one hit and say how long to wait when the cap is reached.

        Args:
            rule: The matched surface.
            client: Client address, as the ASGI server resolved it.

        Returns:
            Seconds to wait, or None when the request is allowed.
        """
        now = time.monotonic()
        key = (rule.path, client)
        bucket = self._hits[key]

        while bucket and now - bucket[0] >= rule.window_seconds:
            bucket.popleft()

        if len(bucket) >= rule.limit:
            return max(1, int(rule.window_seconds - (now - bucket[0])))

        bucket.append(now)
        self._evict_if_needed(key)
        return None

    def _evict_if_needed(self, keep: tuple[str, str]) -> None:
        if len(self._hits) <= _MAX_TRACKED_KEYS:
            return
        for key in list(self._hits):
            if key != keep:
                del self._hits[key]
                break
