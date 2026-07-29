"""Content adapter.

`get_home_content()` is the single entry point every router uses. With
`CONTENT_SOURCE=airtable` it pulls live rows from the WEBSITE base once, then
keeps them in memory until `POST /api/content/refresh` clears the cache.
"""
from __future__ import annotations

import json
from typing import List, Optional

from ..config import settings
from ..models import AboutContent, FellowContent, HomeContent, PeopleContent

_home_cache: Optional[HomeContent] = None
_people_cache: Optional[PeopleContent] = None
_about_cache: Optional[AboutContent] = None
_fellow_cache: Optional[FellowContent] = None
_fellow_pool_cache: Optional[list] = None


def _sync_dynamic_if_due(force: bool = False) -> None:
    """Write `dynamic` ticks to Airtable — only on explicit refresh."""
    if not force:
        return
    if not settings.airtable_sync_dynamic:
        return
    if not _airtable_on():
        return
    from .airtable import sync_dynamic_checkboxes

    try:
        sync_dynamic_checkboxes()
    except Exception as exc:
        print(f"[content] Airtable dynamic sync failed: {exc}")


def _airtable_on() -> bool:
    return bool(
        settings.content_source == "airtable"
        and settings.airtable_api_key
        and settings.airtable_base_id
    )


def get_home_fellow_pool():
    """Cached list of all eligible homepage fellows (Airtable or seed)."""
    global _fellow_pool_cache
    from ..models import Fellow

    if _fellow_pool_cache is not None:
        return _fellow_pool_cache

    pool: List[Fellow] = []
    if _airtable_on():
        from .airtable import build_home_fellow_pool

        pool = build_home_fellow_pool()
    if not pool:
        pool = list(_load_seed().fellows)

    _fellow_pool_cache = pool
    return pool


def get_fellow_spotlight():
    from .airtable import pick_fellow_spotlight
    from ..config import settings

    return pick_fellow_spotlight(get_home_fellow_pool(), settings.home_fellows_spotlight_count)


def get_home_content() -> HomeContent:
    global _home_cache
    if _home_cache is not None:
        content = _home_cache.model_copy(deep=True)
    else:
        seed = _load_seed()
        if _airtable_on():
            from .airtable import build_home_content
            try:
                content = build_home_content(seed)
            except Exception as exc:  # never let a CMS hiccup take the site down
                print(f"[content] Airtable fetch failed, serving seed: {exc}")
                content = seed
        else:
            content = seed

        _home_cache = content
        content = content.model_copy(deep=True)

    content.fellows = get_fellow_spotlight()
    return content


def get_people() -> PeopleContent:
    """Trustees / directors / team / fellows, pulled from Airtable `people`."""
    global _people_cache
    if _people_cache is not None:
        return _people_cache

    empty = PeopleContent(trustees=[], directors=[], team=[], fellows=[], alumni=[], challengers=[])
    if not _airtable_on():
        _people_cache = empty
        return empty

    from .airtable import build_people
    try:
        content = build_people()
    except Exception as exc:
        print(f"[content] Airtable people fetch failed: {exc}")
        content = empty

    _people_cache = content
    return content


def get_about_content() -> AboutContent:
    global _about_cache
    if _about_cache is not None:
        return _about_cache

    seed = _load_about_seed()
    if _airtable_on():
        from .airtable import build_about_content
        try:
            content = build_about_content(seed)
        except Exception as exc:
            print(f"[content] Airtable about fetch failed, serving seed: {exc}")
            content = seed
    else:
        content = seed

    _about_cache = content
    return content


def get_fellow_content() -> FellowContent:
    """Fellow program page content from seed + Airtable `fellow` overrides."""
    global _fellow_cache
    if _fellow_cache is not None:
        return _fellow_cache

    seed = _load_fellow_seed()
    if _airtable_on():
        from .airtable import build_fellow_content
        try:
            content = build_fellow_content(seed)
        except Exception as exc:
            print(f"[content] Airtable fellow fetch failed, serving seed: {exc}")
            content = seed
    else:
        content = seed

    _fellow_cache = content
    return content


def _load_seed() -> HomeContent:
    path = settings.data_dir / "home_content.json"
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    return HomeContent.model_validate(raw)


def _load_about_seed() -> AboutContent:
    path = settings.data_dir / "about_content.json"
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    return AboutContent.model_validate(raw)


def _load_fellow_seed() -> FellowContent:
    path = settings.data_dir / "fellow_content.json"
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    return FellowContent.model_validate(raw)


def reload_content() -> None:
    """Drop in-memory caches and re-pull from Airtable on the next request."""
    global _home_cache, _people_cache, _about_cache, _fellow_cache, _fellow_pool_cache
    from .airtable import clear_publish_meta_cache

    clear_publish_meta_cache()
    _home_cache = None
    _people_cache = None
    _about_cache = None
    _fellow_cache = None
    _fellow_pool_cache = None
    _sync_dynamic_if_due(force=True)
