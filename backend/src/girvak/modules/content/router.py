"""
Module: girvak/modules/content/router.py
Layer: Router
Purpose: The public content URLs. Serializes a page payload once, gives it an
         ETag so an unchanged page costs a 304, and exposes the operator call
         that drops the snapshot.

Dependencies:
    - SettingsDep: cache header values
    - require_admin: guards the refresh call

Called by: http/router.py (mount list)
Calls: modules/content/service.py
"""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel
from starlette.responses import JSONResponse

from girvak.config import Settings
from girvak.http.deps import SettingsDep, require_admin
from girvak.infra.airtable.client import client as airtable_client
from girvak.infra.cache.snapshot import cache
from girvak.infra.storage.media_mirror import mirror
from girvak.modules.content.schemas import (
    AboutContent,
    FellowContent,
    HomeContent,
    PeopleContent,
)
from girvak.modules.content.service import ContentService

router = APIRouter(prefix="/v1/content", tags=["content"])


def _service(settings: Settings) -> ContentService:
    return ContentService(settings, cache(), mirror(), airtable_client())


@router.get("/home", response_model=HomeContent, summary="Home page content")
async def home(request: Request, settings: SettingsDep) -> Response:
    """Content for `/`."""
    return _page(request, await _service(settings).home(), settings)


@router.get("/about", response_model=AboutContent, summary="About page content")
async def about(request: Request, settings: SettingsDep) -> Response:
    """Content for `/about`."""
    return _page(request, await _service(settings).about(), settings)


@router.get("/fellow", response_model=FellowContent, summary="Fellow program content")
async def fellow(request: Request, settings: SettingsDep) -> Response:
    """Content for `/fellow-program`."""
    return _page(request, await _service(settings).fellow_program(), settings)


@router.get("/people", response_model=PeopleContent, summary="People, grouped")
async def people(request: Request, settings: SettingsDep) -> Response:
    """Trustees, directors, team, fellows, alumni, and challengers."""
    return _page(request, await _service(settings).people(), settings)


@router.post(
    "/refresh",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
    summary="Drop the content snapshot",
    responses={
        401: {"description": "UNAUTHENTICATED"},
        429: {"description": "RATE_LIMIT_EXCEEDED"},
    },
)
async def refresh(settings: SettingsDep) -> dict[str, str]:
    """Publish now: the next request re-reads Airtable.

    Operator call, guarded by the admin token and rate-limited by the transport
    layer. Nothing is written to Airtable.
    """
    _service(settings).refresh()
    return {"status": "refreshed"}


def _page(request: Request, payload: BaseModel, settings: Settings) -> Response:
    """Serialize a page once, then answer with it or with a 304.

    Args:
        request: The incoming request, read for If-None-Match.
        payload: The page model.
        settings: Source of the cache-header values.

    Returns:
        200 with the payload, or 304 when the client already has this version.
    """
    body = payload.model_dump_json().encode("utf-8")
    etag = f'"{hashlib.sha256(body).hexdigest()[:16]}"'
    headers = {
        "ETag": etag,
        "Cache-Control": (
            f"public, max-age={settings.content.http_max_age_seconds}, "
            f"stale-while-revalidate={settings.content.http_stale_while_revalidate_seconds}"
        ),
    }

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    return JSONResponse(content=json.loads(body), headers=headers)
