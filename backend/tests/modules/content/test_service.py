"""
Module: tests/modules/content/test_service.py
Layer: Test
Purpose: The snapshot rules: read the source once per TTL, keep serving the last
         good result when the source is down, fall back to the seed, and re-read
         after a refresh.

Dependencies: none
Called by: pytest
Calls: girvak/modules/content/service.py
"""

from __future__ import annotations

import pytest
from tests.modules.content.builders import record

from girvak.config import Settings
from girvak.infra.airtable.client import AirtableRecord
from girvak.infra.cache.snapshot import SnapshotCache
from girvak.infra.storage.media_mirror import MediaMirror
from girvak.modules.content import seeds
from girvak.modules.content.service import ContentService
from girvak.shared.errors import ServiceUnavailableError


class FakeSource:
    """Rows in, call count out."""

    def __init__(self, rows: dict[str, list[AirtableRecord]] | None = None) -> None:
        self.rows = rows or {}
        self.calls: list[str] = []
        self.fail = False

    async def list_records(self, table: str) -> list[AirtableRecord]:
        self.calls.append(table)
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
