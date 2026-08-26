"""
Module: tests/http/test_rate_limit.py
Layer: Test
Purpose: The cap on a public write surface, exercised without a database: the
         limiter answers before routing.

Dependencies: none
Called by: pytest
Calls: girvak/http/middleware/rate_limit.py
"""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from girvak.config import Settings
from girvak.http.middleware.rate_limit import RateLimitMiddleware


def _app(settings: Settings) -> Starlette:
    async def accept(request: object) -> JSONResponse:
        return JSONResponse({"ok": True}, status_code=201)

    application = Starlette(routes=[Route("/v1/newsletter", accept, methods=["POST"])])
    application.add_middleware(RateLimitMiddleware, settings=settings)
    return application


async def test_requests_under_the_cap_reach_the_route(settings: Settings) -> None:
    capped = settings.model_copy(
        update={"limits": settings.limits.model_copy(update={"newsletter_per_ip_per_hour": 2})}
    )
    async with AsyncClient(
        transport=ASGITransport(app=_app(capped)), base_url="http://testserver"
    ) as client:
        first = await client.post("/v1/newsletter", json={})
        second = await client.post("/v1/newsletter", json={})

    assert [first.status_code, second.status_code] == [201, 201]


async def test_request_over_the_cap_is_rejected_with_retry_after(settings: Settings) -> None:
    capped = settings.model_copy(
        update={"limits": settings.limits.model_copy(update={"newsletter_per_ip_per_hour": 1})}
    )
    async with AsyncClient(
        transport=ASGITransport(app=_app(capped)), base_url="http://testserver"
    ) as client:
        await client.post("/v1/newsletter", json={})
        blocked = await client.post("/v1/newsletter", json={})

    assert blocked.status_code == 429
    assert blocked.json()["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert int(blocked.headers["Retry-After"]) > 0


async def test_an_uncapped_url_is_not_limited(settings: Settings) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_app(settings)), base_url="http://testserver"
    ) as client:
        responses = [(await client.get("/health")).status_code for _ in range(30)]

    assert 429 not in responses
