"""Content adapter.

`get_home_content()` is the single entry point every router uses. With
`CONTENT_SOURCE=airtable` it pulls live rows from the WEBSITE base once, then
keeps them in memory until `POST /api/content/refresh` clears the cache (or
`CONTENT_CACHE=false` for live editing).
"""
from __future__ import annotations

import json
from typing import List, Optional

from ..config import settings
from ..models import AboutContent, FellowContent, HomeContent, PeopleContent, Person

_home_cache: Optional[HomeContent] = None
_people_cache: Optional[PeopleContent] = None
_about_cache: Optional[AboutContent] = None
_fellow_cache: Optional[FellowContent] = None
_fellow_pool_cache: Optional[list] = None


def _cache_on() -> bool:
    return settings.content_cache_enabled


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

    if _cache_on() and _fellow_pool_cache is not None:
        return _fellow_pool_cache

    pool: List[Fellow] = []
    if _airtable_on():
        from .airtable import build_home_fellow_pool

        pool = build_home_fellow_pool()
    else:
        pool = list(_load_seed().fellows)

    if _cache_on():
        _fellow_pool_cache = pool
    return pool


def get_fellow_spotlight():
    from .airtable import pick_fellow_spotlight

    return pick_fellow_spotlight(get_home_fellow_pool(), settings.home_fellows_spotlight_count)


def get_fellow_people_spotlight() -> List[Person]:
    """Random homepage fellow cards from live `people` rows (matches fellow page cards)."""
    from .airtable import pick_people_spotlight

    people = get_people()
    pool = [p for p in people.fellows if p.photo]
    if not pool and _airtable_on():
        return []
    return pick_people_spotlight(pool, settings.home_fellows_spotlight_count)


def get_home_content() -> HomeContent:
    global _home_cache
    if _cache_on() and _home_cache is not None:
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

        if _cache_on():
            _home_cache = content
        content = content.model_copy(deep=True)

    content.fellows = get_fellow_spotlight()
    return content


def get_people() -> PeopleContent:
    """Trustees / directors / team / fellows, pulled from Airtable `people`."""
    global _people_cache
    if _cache_on() and _people_cache is not None:
        return _people_cache

    # Fallback: when Airtable is unavailable (e.g. 403 / network issues),
    # at least show the seed `fellows` so image cards don't go blank.
    # Note: trustees/directors/team/alumni/challengers have no seed snapshot.
    def _seed_people_fellows_fallback() -> list[Person]:
        seed = _load_seed()
        out: list[Person] = []
        for f in getattr(seed, "fellows", []) or []:
            name = getattr(f, "name", "") or ""
            parts = name.strip().split()
            first = parts[0] if parts else ""
            last = " ".join(parts[1:]) if len(parts) > 1 else ""
            out.append(
                Person(
                    first=first,
                    last=last,
                    company=getattr(f, "university", "") or "",
                    position=getattr(f, "department", "") or "",
                    university=getattr(f, "university", "") or "",
                    department=getattr(f, "department", "") or "",
                    photo=getattr(f, "image", "") or "",
                    linkedin="",
                    roles=["seed:fellow"],
                    year=getattr(f, "year", "") or "",
                )
            )
        return out

    seed_people = _seed_people_fellows_fallback()
    fallback = PeopleContent(
        # Airtable unavailable → avoid blank pages by showing seed people for
        # all groups. Real data will replace this once Airtable is reachable.
        trustees=seed_people,
        directors=seed_people,
        team=seed_people,
        fellows=seed_people,
        alumni=seed_people,
        challengers=seed_people,
    )

    empty = PeopleContent(
        trustees=[], directors=[], team=[], fellows=[], alumni=[], challengers=[]
    )
    if not _airtable_on():
        if _cache_on():
            _people_cache = fallback
        return fallback

    from .airtable import build_people
    try:
        content = build_people()
    except Exception as exc:
        print(f"[content] Airtable people fetch failed: {exc}")
        content = fallback

    if _cache_on():
        # If Airtable returned empty lists (common when it errors but doesn't throw),
        # keep the seed fallback to avoid blank UI.
        if (
            not content.trustees
            and not content.directors
            and not content.team
            and not content.fellows
            and not content.alumni
            and not content.challengers
        ):
            content = fallback
        else:
            # Partial failures are common: e.g. `fellows` may exist but
            # trustees/directors/team are empty. Fill missing groups too.
            if not content.trustees:
                content.trustees = fallback.trustees
            if not content.directors:
                content.directors = fallback.directors
            if not content.team:
                content.team = fallback.team
            if not content.alumni:
                content.alumni = fallback.alumni
            if not content.challengers:
                content.challengers = fallback.challengers
        _people_cache = content
    return content


def get_about_content() -> AboutContent:
    global _about_cache
    if _cache_on() and _about_cache is not None:
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

    if _cache_on():
        _about_cache = content
    return content


def get_fellow_content() -> FellowContent:
    """Fellow program page content from seed + Airtable `fellow` overrides."""
    global _fellow_cache
    if _cache_on() and _fellow_cache is not None:
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

    if _cache_on():
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


def reload_content(sync_dynamic: bool = True) -> None:
    """Drop in-memory caches and re-pull from Airtable on the next request.

    If `sync_dynamic` is False, we only clear caches (no Airtable "dynamic"
    checkbox sync), which is safer for polling-based invalidation.
    """
    global _home_cache, _people_cache, _about_cache, _fellow_cache, _fellow_pool_cache
    from .airtable import clear_publish_meta_cache
    from .media import reset_failures

    clear_publish_meta_cache()
    # Give attachments whose mirror download failed another chance.
    reset_failures()
    _home_cache = None
    _people_cache = None
    _about_cache = None
    _fellow_cache = None
    _fellow_pool_cache = None
    if sync_dynamic:
        _sync_dynamic_if_due(force=True)
