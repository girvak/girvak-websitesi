"""
Module: tests/modules/newsletter/test_router.py
Layer: Test
Purpose: The public contract of POST /v1/newsletter — status codes and
         error_code, not message copy.

Dependencies: none
Called by: pytest
Calls: girvak/modules/newsletter/router.py
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.db


async def test_subscribe_returns_201(db_client: AsyncClient) -> None:
    response = await db_client.post("/v1/newsletter", json={"email": "abone@example.com"})

    assert response.status_code == 201
    assert response.json()["message"]


async def test_duplicate_returns_409_with_error_code(db_client: AsyncClient) -> None:
    await db_client.post("/v1/newsletter", json={"email": "abone@example.com"})

    response = await db_client.post("/v1/newsletter", json={"email": "abone@example.com"})

    assert response.status_code == 409
    assert response.json()["error_code"] == "NEWSLETTER_ALREADY_SUBSCRIBED"


async def test_malformed_email_returns_422_with_field_names(db_client: AsyncClient) -> None:
    response = await db_client.post("/v1/newsletter", json={"email": "not-an-email"})

    body = response.json()
    assert response.status_code == 422
    assert body["error_code"] == "VALIDATION_ERROR"
    assert "email" in body["details"]["fields"]


async def test_unknown_field_is_rejected(db_client: AsyncClient) -> None:
    response = await db_client.post(
        "/v1/newsletter", json={"email": "abone@example.com", "role": "admin"}
    )

    assert response.status_code == 422
