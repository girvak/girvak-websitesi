"""
Module: tests/modules/content/test_router.py
Layer: Test
Purpose: The public content contract: payload, cache headers, the 304, and who
         may drop the snapshot.

Dependencies: none
Called by: pytest
Calls: girvak/modules/content/router.py
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from tests.conftest import ADMIN_TOKEN

PAGES = ("home", "about", "fellow", "people")


@pytest.mark.parametrize("page", PAGES)
async def test_every_page_answers_with_content(client: AsyncClient, page: str) -> None:
    response = await client.get(f"/v1/content/{page}")

    assert response.status_code == 200
    assert response.json()


async def test_home_payload_carries_the_sections_the_page_renders(client: AsyncClient) -> None:
    body = (await client.get("/v1/content/home")).json()

    assert body["hero"]["rotator_words"]
    assert len(body["impact"]) > 0
    assert body["footer"]["contact"]["email"]


@pytest.mark.parametrize("page", PAGES)
async def test_response_is_cacheable_and_tagged(client: AsyncClient, page: str) -> None:
    response = await client.get(f"/v1/content/{page}")

    assert response.headers["ETag"]
    assert "max-age" in response.headers["Cache-Control"]
    assert "stale-while-revalidate" in response.headers["Cache-Control"]


async def test_unchanged_content_costs_a_304(client: AsyncClient) -> None:
    first = await client.get("/v1/content/home")

    second = await client.get("/v1/content/home", headers={"If-None-Match": first.headers["ETag"]})

    assert second.status_code == 304
    assert second.content == b""


async def test_a_different_etag_still_returns_the_body(client: AsyncClient) -> None:
    response = await client.get("/v1/content/home", headers={"If-None-Match": '"stale"'})

    assert response.status_code == 200


async def test_refresh_without_the_admin_token_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/v1/content/refresh")

    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHENTICATED"


async def test_refresh_with_a_wrong_token_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/v1/content/refresh", headers={"X-Admin-Token": "not-the-token"})

    assert response.status_code == 401


async def test_refresh_with_the_admin_token_is_accepted(client: AsyncClient) -> None:
    response = await client.post("/v1/content/refresh", headers={"X-Admin-Token": ADMIN_TOKEN})

    assert response.status_code == 202
    assert response.json() == {"status": "refreshed"}


async def test_every_response_carries_the_security_headers(client: AsyncClient) -> None:
    response = await client.get("/v1/content/home")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
