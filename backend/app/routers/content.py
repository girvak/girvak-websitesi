"""Content API — serves the structured home-page payload."""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..config import settings
from ..models import AboutContent, Fellow, FellowContent, HomeContent, PeopleContent, Person
from ..security import refresh_limiter, require_admin
from ..services.airtable import publish_guide
from ..services.content_source import (
    get_about_content,
    get_fellow_content,
    get_fellow_people_spotlight,
    get_fellow_spotlight,
    get_home_content,
    get_people,
    reload_content,
)
from ..services.media import stats as media_stats

router = APIRouter(prefix="/api/content", tags=["content"])


def _cache_control(response: Response) -> None:
    if settings.content_cache_enabled:
        response.headers["Cache-Control"] = "public, max-age=86400, must-revalidate"
    else:
        response.headers["Cache-Control"] = "no-store"


def _etag(content: HomeContent) -> str:
    body = content.model_dump_json().encode("utf-8")
    return '"' + hashlib.sha256(body).hexdigest()[:16] + '"'


@router.get("/home", response_model=HomeContent)
def home(request: Request, response: Response) -> HomeContent:
    content = get_home_content()
    etag = _etag(content)
    response.headers["ETag"] = etag
    _cache_control(response)

    if request.headers.get("if-none-match") == etag:
        # Content unchanged — let the client reuse its copy.
        return Response(status_code=304, headers={"ETag": etag})  # type: ignore[return-value]

    return content


@router.get("/people", response_model=PeopleContent)
def people(request: Request, response: Response) -> PeopleContent:
    content = get_people()
    body = content.model_dump_json().encode("utf-8")
    etag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'
    response.headers["ETag"] = etag
    _cache_control(response)

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})  # type: ignore[return-value]

    return content


@router.get("/about", response_model=AboutContent)
def about_page(request: Request, response: Response) -> AboutContent:
    content = get_about_content()
    body = content.model_dump_json().encode("utf-8")
    etag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'
    response.headers["ETag"] = etag
    _cache_control(response)

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})  # type: ignore[return-value]

    return content


@router.get("/fellow", response_model=FellowContent)
def fellow_page(request: Request, response: Response) -> FellowContent:
    content = get_fellow_content()
    body = content.model_dump_json().encode("utf-8")
    etag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'
    response.headers["ETag"] = etag
    _cache_control(response)

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})  # type: ignore[return-value]

    return content


@router.get("/fellows-spotlight", response_model=list[Person])
def fellows_spotlight(response: Response) -> list[Person]:
    """Random homepage fellow cards (new sample on every request)."""
    response.headers["Cache-Control"] = "no-store"
    return get_fellow_people_spotlight()


@router.get("/fellows-spotlight-legacy", response_model=list[Fellow], include_in_schema=False)
def fellows_spotlight_legacy(response: Response) -> list[Fellow]:
    response.headers["Cache-Control"] = "no-store"
    return get_fellow_spotlight()


@router.get("/publish-guide", include_in_schema=False)
def airtable_publish_guide() -> dict:
    """Which Airtable rows the site uses — internal debug only."""
    if not settings.enable_debug_routes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    guide = publish_guide()
    from ..services.airtable import (
        _about_used_ids,
        _dynamic_column,
        _dynamic_field_names,
        _fellow_used_ids,
        _home_used_ids,
        _meta_checkbox_fields,
        _partner_used_ids,
        _people_used_ids,
        _safe,
    )

    used_fns = {
        settings.airtable_table_home: _home_used_ids,
        settings.airtable_table_about: _about_used_ids,
        settings.airtable_table_people: _people_used_ids,
        settings.airtable_table_partner: _partner_used_ids,
        settings.airtable_table_fellow: _fellow_used_ids,
    }
    detected: dict[str, dict] = {}
    for table in (
        settings.airtable_table_home,
        settings.airtable_table_about,
        settings.airtable_table_people,
        settings.airtable_table_partner,
        settings.airtable_table_fellow,
    ):
        rows = _safe(table)
        keys = _dynamic_field_names(rows, table)
        meta = _meta_checkbox_fields(table)
        used_fn = used_fns.get(table)
        site_used = len(used_fn(rows)) if used_fn else None
        detected[table] = {
            "dynamic_column": keys[0] if keys else _dynamic_column(table, rows),
            "all_checkbox_columns": meta,
            "site_used_rows": site_used,
            "total_rows": len(rows),
        }
    guide["dynamic_sync"] = detected
    guide["media_mirror"] = media_stats()
    return guide


@router.post("/refresh", dependencies=[Depends(require_admin), Depends(refresh_limiter.dependency())])
def refresh() -> dict:
    """Clear the cached content so the next request re-pulls from Airtable.

    Also re-syncs `dynamic` checkboxes in Airtable when AIRTABLE_SYNC_DYNAMIC=true.
    Requires X-Admin-Token header.
    """
    reload_content()
    return {"status": "refreshed"}
