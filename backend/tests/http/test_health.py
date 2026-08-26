"""
Module: tests/http/test_health.py
Layer: Test
Purpose: The liveness route and the two transport guarantees every response
         carries: a correlation id, and the one error body shape.

Dependencies: none
Called by: pytest
Calls: girvak/http/router.py, girvak/http/middleware/request_id.py, girvak/http/errors/
"""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_ok_without_touching_a_dependency(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_response_echoes_a_generated_request_id(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.headers["X-Request-ID"]


async def test_response_echoes_the_client_request_id(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["X-Request-ID"] == "abc-123"


async def test_client_request_id_is_stripped_of_unsafe_characters(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "a b\tc<script>"})

    assert response.headers["X-Request-ID"] == "abcscript"


async def test_unknown_path_returns_the_one_error_body(client: AsyncClient) -> None:
    response = await client.get("/v1/nope")

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "NOT_FOUND"
    assert body["details"] == {}
    assert body["message"]
