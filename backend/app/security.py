"""Shared security helpers — URL validation, admin auth, rate limiting."""
from __future__ import annotations

import logging
import secrets
import time
from collections import defaultdict
from threading import Lock
from typing import Callable
from urllib.parse import urlparse

from fastapi import Header, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .config import settings

logger = logging.getLogger(__name__)

ALLOWED_HREF_SCHEMES = frozenset({"http", "https", "mailto", "tel"})
ALLOWED_IMAGE_SCHEMES = frozenset({"http", "https"})


def safe_href(url: str, fallback: str = "#") -> str:
    """Return a safe link target; reject javascript:, data:, etc."""
    url = (url or "").strip()
    if not url:
        return fallback
    if url.startswith("#") or url.startswith("/"):
        return url
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_HREF_SCHEMES:
        return fallback
    return url


def safe_image_src(url: str, fallback: str = "") -> str:
    """Return a safe image URL; allow relative /media and /images paths."""
    url = (url or "").strip()
    if not url:
        return fallback
    if url.startswith("/"):
        return url
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_IMAGE_SCHEMES:
        return fallback
    return url


def require_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> None:
    """Protect admin-only endpoints with a shared secret header."""
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoints are disabled",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.admin_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def require_ajax(request: Request) -> None:
    """Block simple cross-site form posts (CSRF mitigation for JSON endpoints)."""
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


class RateLimiter:
    """Simple in-memory sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits[key]
            self._hits[key] = bucket = [t for t in bucket if t > cutoff]
            if len(bucket) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests",
                )
            bucket.append(now)

    def dependency(self) -> Callable[[Request], None]:
        def _dep(request: Request) -> None:
            client = request.client.host if request.client else "unknown"
            self.check(client)

        return _dep


newsletter_limiter = RateLimiter(max_requests=5, window_seconds=60)
refresh_limiter = RateLimiter(max_requests=3, window_seconds=60)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
