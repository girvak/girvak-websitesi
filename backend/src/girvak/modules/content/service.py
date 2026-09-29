"""
Module: girvak/modules/content/service.py
Layer: Service
Purpose: The one way a page gets its content. Reads Airtable at most once per
         TTL, keeps the last good result for an outage, and falls back to the
         committed seed. Sending anything back to Airtable is not done here —
         this side of the system only reads.

Dependencies:
    - Settings: source, TTL, table names, spotlight size
    - SnapshotCache: the per-process snapshot
    - MediaMirror: non-expiring image URLs
    - RecordSource: the rows (absent when the source is the seed)

Called by: modules/content/router.py
Calls: infra/airtable/client.py, infra/cache/snapshot.py,
       infra/storage/media_mirror.py, modules/content/{home,about,fellow,people,seeds}.py
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol, TypeVar, cast

from girvak.config import Settings
from girvak.infra.airtable.client import AirtableRecord
from girvak.infra.cache.snapshot import SnapshotCache
from girvak.infra.storage.media_mirror import AttachmentRef, MediaMirror
from girvak.modules.content import about as about_page
from girvak.modules.content import fellow as fellow_page
from girvak.modules.content import home as home_page
from girvak.modules.content import people as people_page
from girvak.modules.content import seeds
from girvak.modules.content import ventures as ventures_page
from girvak.modules.content.fragments import FULL, LARGE, Fragments, collect_refs, logo_refs
from girvak.modules.content.schemas import (
    AboutContent,
    Fellow,
    FellowContent,
    HomeContent,
    PeopleContent,
    VenturesContent,
)
from girvak.modules.content.ventures import VenturesData
from girvak.shared.errors import ServiceUnavailableError
from girvak.shared.logging import LoggerName, get_logger

_logger = get_logger(LoggerName.SYSTEM)

# How many fellow cards the home belt shows. A display rule, so it lives with
# the page rather than in Settings.
SPOTLIGHT_COUNT = 8

HOME_KEY = "home"
ABOUT_KEY = "about"
FELLOW_KEY = "fellow"
PEOPLE_KEY = "people"
VENTURES_KEY = "ventures"

ValueT = TypeVar("ValueT")


class RecordSource(Protocol):
    """What this service needs from a content source: rows of a named table.

    Typed as a capability rather than as AirtableClient so the page rules never
    depend on the vendor, and so a test can hand in rows directly.
    """

    async def list_records(self, table: str) -> list[AirtableRecord]:
        """Return every row of one table."""
        ...


class ContentService:
    """Page content, as the site reads it."""

    def __init__(
        self,
        settings: Settings,
        cache: SnapshotCache,
        mirror: MediaMirror,
        client: RecordSource | None,
    ) -> None:
        self._settings = settings
        self._cache = cache
        self._mirror = mirror
        self._client = client

    async def home(self) -> HomeContent:
        """The home page.

        The fellow belt is sampled when the snapshot is built, not per request,
        so the payload has a stable ETag for the length of one TTL window.

        Returns:
            Home content — from Airtable, the last good snapshot, or the seed.
        """
        return await self._snapshot(HOME_KEY, self._build_home, seeds.home)

    async def about(self) -> AboutContent:
        """The about page.

        Returns:
            About content — from Airtable, the last good snapshot, or the seed.
        """
        return await self._snapshot(ABOUT_KEY, self._build_about, seeds.about)

    async def fellow_program(self) -> FellowContent:
        """The fellow-program page.

        Returns:
            Fellow content — from Airtable, the last good snapshot, or the seed.
        """
        return await self._snapshot(FELLOW_KEY, self._build_fellow, seeds.fellow)

    async def people(self) -> PeopleContent:
        """Trustees, directors, team, fellows, alumni, challengers.

        Returns:
            People content. There is no seed for people, so an outage with no
            previous snapshot returns empty groups and the page renders its
            empty state rather than inventing names.
        """
        return await self._snapshot(PEOPLE_KEY, self._build_people, _empty_people)

    async def ventures(
        self,
        *,
        kind: ventures_page.Kind = "ventures",
        sectors: Sequence[str] = (),
        programs: Sequence[str] = (),
        years: Sequence[str] = (),
        q: str = "",
        page: int = 1,
        per_page: int = ventures_page.DEFAULT_PER_PAGE,
    ) -> VenturesContent:
        """One page of one tab of the founders & ventures directory.

        The whole directory is mapped once per TTL and the filter and page
        number are applied to that snapshot, so paging and filtering cost
        Airtable nothing — only the first request after a TTL expiry reads it.

        Args:
            kind: Which tab to page through — `ventures` or `founders`.
            sectors: Sector slugs to keep; empty means every sector.
            programs: Programme slugs to keep; empty means every programme.
            years: Cohort keys (`26`) to keep; empty means every cohort.
            q: Free text over name, description and founder names.
            page: 1-based page number, clamped to the last page.
            per_page: Cards per page, capped by the mapping.

        Returns:
            The page payload, with facet counts and the echoed filter.
        """
        data = await self._snapshot(VENTURES_KEY, self._build_ventures, _empty_ventures)
        return ventures_page.select(
            data,
            kind=kind,
            sectors=sectors,
            programs=programs,
            years=years,
            q=q,
            page=page,
            per_page=per_page,
        )

    def refresh(self) -> None:
        """Drop the snapshots so the next request re-reads Airtable.

        Fallbacks are kept, and downloads that failed are allowed to retry.
        """
        self._cache.clear()
        self._mirror.reset_failures()
        _logger.info("content_cache_cleared")

    async def _snapshot(
        self,
        key: str,
        build: Callable[[], Awaitable[ValueT]],
        fallback: Callable[[], ValueT],
    ) -> ValueT:
        cached = cast(ValueT | None, self._cache.get(key))
        if cached is not None:
            return cached

        async with self._cache.lock(key):
            # Another request may have filled it while this one waited.
            cached = cast(ValueT | None, self._cache.get(key))
            if cached is not None:
                return cached

            try:
                value = await build()
            except ServiceUnavailableError as exc:
                stale = cast(ValueT | None, self._cache.get_fallback(key))
                _logger.warning(
                    "content_source_unavailable",
                    extra={"page": key, "served": "stale" if stale else "seed", "reason": str(exc)},
                )
                return stale if stale is not None else fallback()

            self._cache.set(key, value)
            self._cache.set_fallback(key, value)
            return value

    def _media_urls(self, refs: list[AttachmentRef]) -> dict[str, str]:
        """URLs for a set of attachments, without waiting on any download.

        Missing files are handed out as Airtable URLs and fetched in the
        background, so a cold mirror slows nothing down (16-performance: vendor
        I/O does not belong in a request).

        Args:
            refs: Attachments this page needs.

        Returns:
            The URL map the mapping pass reads.
        """
        urls, missing = self._mirror.resolve(refs)
        self._mirror.fetch_in_background(missing)
        return urls

    async def _build_home(self) -> HomeContent:
        seed = seeds.home()
        if self._client is None:
            return seed

        tables = self._settings.airtable
        home_records = await self._client.list_records(tables.table_home)
        partner_records = await self._client.list_records(tables.table_partner)
        media = self._media_urls(collect_refs(home_records, FULL) + logo_refs(partner_records))

        content = home_page.build(
            seed,
            Fragments(home_records, media),
            Fragments(partner_records, media),
        )

        belt = await self._fellow_belt()
        return content.model_copy(update={"fellows": belt}) if belt else content

    async def _build_about(self) -> AboutContent:
        seed = seeds.about()
        if self._client is None:
            return seed
        records = await self._client.list_records(self._settings.airtable.table_about)
        media = self._media_urls(collect_refs(records, FULL))
        return about_page.build(seed, Fragments(records, media))

    async def _build_fellow(self) -> FellowContent:
        seed = seeds.fellow()
        if self._client is None:
            return seed
        records = await self._client.list_records(self._settings.airtable.table_fellow)
        media = self._media_urls(collect_refs(records, FULL))
        return fellow_page.build(seed, Fragments(records, media))

    async def _build_ventures(self) -> VenturesData:
        copy = seeds.ventures()
        if self._client is None:
            return VenturesData(copy=copy, items=(), founders=())

        tables = self._settings.airtable
        venture_records = await self._client.list_records(tables.table_ventures)
        sector_records = await self._client.list_records(tables.table_sectors)
        program_records = await self._client.list_records(tables.table_programs)
        people_records = await self._client.list_records(tables.table_people)

        media = self._media_urls(ventures_page.media_refs(venture_records, people_records))
        return ventures_page.build(
            copy, venture_records, sector_records, program_records, people_records, media
        )

    async def _build_people(self) -> PeopleContent:
        if self._client is None:
            return _empty_people()
        records = await self._client.list_records(self._settings.airtable.table_people)
        return people_page.build(Fragments(records, self._people_media(records)))

    def _people_media(self, records: list[AirtableRecord]) -> dict[str, str]:
        # Person cards render at 200-400px, so they use Airtable's `large`
        # rendition; `full` cost roughly twelve times the bytes for no visible
        # gain and made the trustees page enormous.
        return self._media_urls(collect_refs(records, LARGE, "photo", "attachments", "image"))

    async def _fellow_belt(self) -> list[Fellow]:
        """Sample the home belt from the people snapshot.

        Reuses the people snapshot instead of pulling the table a second time.

        Returns:
            The cards for this snapshot, or an empty list when no fellow has a
            photo yet.
        """
        people = await self.people()
        pool = [
            Fellow(
                year=person.year,
                name=f"{person.first} {person.last}".strip(),
                university=person.university,
                department=person.department,
                image=person.photo,
                color="teal",
            )
            for person in people.fellows
            if person.photo
        ]
        return people_page.spotlight(pool, SPOTLIGHT_COUNT)


def _empty_ventures() -> VenturesData:
    return VenturesData(copy=seeds.ventures(), items=(), founders=())


def _empty_people() -> PeopleContent:
    return PeopleContent(trustees=[], directors=[], team=[], fellows=[], alumni=[], challengers=[])
