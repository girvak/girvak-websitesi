"""
Module: tests/modules/content/test_service.py
Layer: Test
Purpose: The snapshot rules: read the source once per TTL, keep serving the last
         good result when the source is down, fall back to the seed, and re-read
         after a refresh — and never make a visitor wait for a read once a page
         has been built: an expired snapshot is answered from the last copy while
         one rebuild runs behind the request, and a start fills them all first.

Dependencies: none
Called by: pytest
Calls: girvak/modules/content/service.py
"""

from __future__ import annotations

import asyncio

import pytest
from tests.modules.content.builders import record

from girvak.config import Settings
from girvak.infra.airtable.client import AirtableRecord
from girvak.infra.cache.snapshot import SnapshotCache
from girvak.infra.storage.media_mirror import MediaMirror
from girvak.modules.content import seeds
from girvak.modules.content.service import (
    ContentService,
    pending_revalidations,
    warm_up,
)
from girvak.shared.errors import ServiceUnavailableError


class FakeSource:
    """Rows in, call count out."""

    def __init__(self, rows: dict[str, list[AirtableRecord]] | None = None) -> None:
        self.rows = rows or {}
        self.calls: list[str] = []
        self.fail = False
        # While set, a read waits on it: a source that is slow rather than dead.
        self.gate: asyncio.Event | None = None

    async def list_records(self, table: str) -> list[AirtableRecord]:
        self.calls.append(table)
        if self.gate is not None:
            await self.gate.wait()
        if self.fail:
            raise ServiceUnavailableError("İçerik kaynağına ulaşılamıyor.")
        return self.rows.get(table, [])


@pytest.fixture
def cache(app_settings: Settings) -> SnapshotCache:
    return SnapshotCache(app_settings.content.ttl_seconds)


@pytest.fixture
def media(app_settings: Settings) -> MediaMirror:
    return MediaMirror(app_settings)


def _service(
    settings: Settings,
    cache: SnapshotCache,
    media: MediaMirror,
    source: FakeSource | None,
) -> ContentService:
    return ContentService(settings, cache, media, source)


async def test_without_a_source_the_seed_is_served(
    app_settings: Settings, cache: SnapshotCache, media: MediaMirror
) -> None:
    service = _service(app_settings, cache, media, None)

    assert await service.home() == seeds.home()
    assert await service.about() == seeds.about()
    assert await service.fellow_program() == seeds.fellow()


async def test_without_a_source_people_is_empty_rather_than_invented(
    app_settings: Settings, cache: SnapshotCache, media: MediaMirror
) -> None:
    content = await _service(app_settings, cache, media, None).people()

    assert content.trustees == []
    assert content.fellows == []


async def test_source_rows_override_the_seed(
    app_settings: Settings, cache: SnapshotCache, media: MediaMirror
) -> None:
    airtable = app_settings.airtable
    source = FakeSource({airtable.table_about: [record("about_seo_title", text="Hakkımızda")]})

    content = await _service(app_settings, cache, media, source).about()

    assert content.seo_title == "Hakkımızda"


async def test_the_source_is_read_once_per_ttl(
    app_settings: Settings, cache: SnapshotCache, media: MediaMirror
) -> None:
    source = FakeSource()
    service = _service(app_settings, cache, media, source)

    await service.about()
    await service.about()

    assert source.calls.count(app_settings.airtable.table_about) == 1


async def test_a_dead_source_falls_back_to_the_seed(
    app_settings: Settings, cache: SnapshotCache, media: MediaMirror
) -> None:
    source = FakeSource()
    source.fail = True

    content = await _service(app_settings, cache, media, source).about()

    assert content == seeds.about()


async def test_a_source_that_dies_later_keeps_serving_the_last_good_snapshot(
    app_settings: Settings, cache: SnapshotCache, media: MediaMirror
) -> None:
    airtable = app_settings.airtable
    source = FakeSource({airtable.table_about: [record("about_seo_title", text="Canlı")]})
    service = _service(app_settings, cache, media, source)

    await service.about()
    service.refresh()
    source.fail = True

    content = await service.about()

    assert content.seo_title == "Canlı"


async def test_refresh_makes_the_next_read_hit_the_source(
    app_settings: Settings, cache: SnapshotCache, media: MediaMirror
) -> None:
    source = FakeSource()
    service = _service(app_settings, cache, media, source)

    await service.about()
    service.refresh()
    await service.about()

    assert source.calls.count(app_settings.airtable.table_about) == 2


async def test_a_zero_ttl_reads_the_source_every_time(
    app_settings: Settings, media: MediaMirror
) -> None:
    source = FakeSource()
    service = _service(app_settings, SnapshotCache(0), media, source)

    await service.about()
    await service.about()

    assert source.calls.count(app_settings.airtable.table_about) == 2


async def test_home_belt_is_sampled_from_the_people_table(
    app_settings: Settings, cache: SnapshotCache, media: MediaMirror
) -> None:
    airtable = app_settings.airtable
    source = FakeSource(
        {
            airtable.table_people: [
                AirtableRecord(
                    id=f"rec{index}",
                    fields={
                        "name": f"Fellow {index}",
                        "tag": ["fellow"],
                        "university": "Bir Üniversite",
                        "photo": [
                            {
                                "id": f"att{index}",
                                "url": "https://x/p.png",
                                "filename": "p.png",
                                "type": "image/png",
                            }
                        ],
                    },
                )
                for index in range(3)
            ]
        }
    )

    content = await _service(app_settings, cache, media, source).home()

    assert len(content.fellows) == 3
    assert {fellow.university for fellow in content.fellows} == {"Bir Üniversite"}


async def test_a_cold_mirror_does_not_hold_up_the_page(
    app_settings: Settings, cache: SnapshotCache, media: MediaMirror
) -> None:
    """The first render serves Airtable's own URLs; downloads happen after it."""
    airtable = app_settings.airtable
    source = FakeSource(
        {
            airtable.table_about: [
                AirtableRecord(
                    id="rec1",
                    fields={
                        "name": "about_mission_headline",
                        "text": "Misyon",
                        "attachments": [
                            {
                                "id": "attCold1",
                                "url": "https://v5.airtableusercontent.com/x/full.png",
                                "filename": "m.png",
                                "type": "image/png",
                            }
                        ],
                    },
                )
            ]
        }
    )

    content = await _service(app_settings, cache, media, source).about()

    assert content.mission.image == "https://v5.airtableusercontent.com/x/full.png"


# --- No visitor waits on Airtable once a page has been built -------------------


class Clock:
    """Time that moves only when a test says so."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


def _aging_service(
    settings: Settings, media: MediaMirror, source: FakeSource, clock: Clock
) -> ContentService:
    cache = SnapshotCache(settings.content.ttl_seconds, clock)
    return ContentService(settings, cache, media, source)


def _about_rows(settings: Settings, title: str) -> dict[str, list[AirtableRecord]]:
    return {settings.airtable.table_about: [record("about_seo_title", text=title)]}


async def _settle() -> None:
    """Let the rebuilds running behind requests finish."""
    await asyncio.gather(*pending_revalidations())


async def test_an_expired_snapshot_is_served_at_once_and_rebuilt_behind_the_request(
    app_settings: Settings, media: MediaMirror, clock: Clock
) -> None:
    source = FakeSource(_about_rows(app_settings, "Eski"))
    service = _aging_service(app_settings, media, source, clock)
    await service.about()

    source.rows = _about_rows(app_settings, "Yeni")
    clock.now += app_settings.content.ttl_seconds + 1
    source.gate = asyncio.Event()  # the source is now slow

    # The visitor is not made to wait for it.
    served = await asyncio.wait_for(service.about(), timeout=1)
    assert served.seo_title == "Eski"

    source.gate.set()
    await _settle()

    assert (await service.about()).seo_title == "Yeni"
    assert source.calls.count(app_settings.airtable.table_about) == 2


async def test_a_burst_after_expiry_rebuilds_once(
    app_settings: Settings, media: MediaMirror, clock: Clock
) -> None:
    source = FakeSource(_about_rows(app_settings, "Eski"))
    service = _aging_service(app_settings, media, source, clock)
    await service.about()

    clock.now += app_settings.content.ttl_seconds + 1
    source.gate = asyncio.Event()

    served = await asyncio.wait_for(asyncio.gather(*(service.about() for _ in range(6))), 1)
    assert {content.seo_title for content in served} == {"Eski"}

    source.gate.set()
    await _settle()

    # The first build, and one rebuild between the six of them.
    assert source.calls.count(app_settings.airtable.table_about) == 2


async def test_a_failed_rebuild_keeps_the_last_copy_and_backs_off(
    app_settings: Settings, media: MediaMirror, clock: Clock
) -> None:
    table = app_settings.airtable.table_about
    source = FakeSource(_about_rows(app_settings, "Canlı"))
    service = _aging_service(app_settings, media, source, clock)
    await service.about()

    clock.now += app_settings.content.ttl_seconds + 1
    source.fail = True
    assert (await service.about()).seo_title == "Canlı"
    await _settle()
    assert source.calls.count(table) == 2  # one attempt, which failed

    # The next visitors do not each try a source that just failed.
    for _ in range(5):
        assert (await service.about()).seo_title == "Canlı"
    await _settle()
    assert source.calls.count(table) == 2

    # After the back-off it tries again — and when the source is back, it recovers.
    source.fail = False
    source.rows = _about_rows(app_settings, "Yeni")
    clock.now += 31
    assert (await service.about()).seo_title == "Canlı"
    await _settle()
    assert source.calls.count(table) == 3
    assert (await service.about()).seo_title == "Yeni"


async def test_refresh_waits_for_the_source_and_returns_what_it_holds_now(
    app_settings: Settings, media: MediaMirror, clock: Clock
) -> None:
    source = FakeSource(_about_rows(app_settings, "Eski"))
    service = _aging_service(app_settings, media, source, clock)
    await service.about()

    source.rows = _about_rows(app_settings, "Yeni")
    service.refresh()

    # An editor who just asked for a refresh must see the new page, not the old.
    assert (await service.about()).seo_title == "Yeni"
    assert pending_revalidations() == []


async def test_warm_up_fills_every_snapshot(
    app_settings: Settings, cache: SnapshotCache, media: MediaMirror
) -> None:
    source = FakeSource()
    service = _service(app_settings, cache, media, source)

    await warm_up(service)

    read = len(source.calls)
    airtable = app_settings.airtable
    for table in (
        airtable.table_people,
        airtable.table_home,
        airtable.table_about,
        airtable.table_fellow,
        airtable.table_ventures,
    ):
        assert table in source.calls

    await service.home()
    await service.about()
    await service.fellow_program()
    await service.people()
    await service.ventures()
    assert len(source.calls) == read  # the first visitor reads nothing


async def test_warm_up_skips_a_page_that_fails_and_fills_the_rest(
    app_settings: Settings,
    cache: SnapshotCache,
    media: MediaMirror,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = FakeSource()
    service = _service(app_settings, cache, media, source)

    async def broken() -> None:
        raise RuntimeError("this page cannot be built")

    monkeypatch.setattr(service, "about", broken)

    await warm_up(service)  # does not raise

    assert app_settings.airtable.table_home in source.calls
    assert app_settings.airtable.table_ventures in source.calls
