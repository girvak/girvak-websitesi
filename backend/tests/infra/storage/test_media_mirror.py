"""
Module: tests/infra/storage/test_media_mirror.py
Layer: Test
Purpose: What the mirror answers before anything is downloaded, and the filename
         scheme that makes a mirrored file cacheable forever.

Dependencies: none
Called by: pytest
Calls: girvak/infra/storage/media_mirror.py
"""

from __future__ import annotations

import pytest

from girvak.config import Settings
from girvak.infra.storage.media_mirror import MediaMirror, attachment_ref, cache_key

ATTACHMENT = {
    "id": "attTest123",
    "url": "https://v5.airtableusercontent.com/x/orig.png",
    "filename": "photo.png",
    "type": "image/png",
    "thumbnails": {
        "large": {"url": "https://v5.airtableusercontent.com/x/large.png"},
        "full": {"url": "https://v5.airtableusercontent.com/x/full.png"},
    },
}


@pytest.fixture
def mirror(app_settings: Settings) -> MediaMirror:
    return MediaMirror(app_settings)


def test_requested_variant_decides_the_lookup_key() -> None:
    ref = attachment_ref(ATTACHMENT, "large")

    assert ref is not None
    assert cache_key(ref.attachment_id, ref.requested) == "attTest123:large"
    assert ref.remote_url.endswith("large.png")


def test_a_missing_thumbnail_falls_back_to_the_original() -> None:
    ref = attachment_ref({**ATTACHMENT, "thumbnails": {}}, "large")

    assert ref is not None
    assert ref.variant == "orig"
    # The caller still looks it up under what it asked for.
    assert ref.requested == "large"


def test_an_attachment_without_an_id_is_skipped() -> None:
    assert attachment_ref({"url": "https://v5.airtableusercontent.com/x.png"}, "full") is None


def test_nothing_on_disk_yet_resolves_to_the_airtable_url(mirror: MediaMirror) -> None:
    ref = attachment_ref(ATTACHMENT, "full")
    assert ref is not None

    urls, missing = mirror.resolve([ref])

    assert urls[cache_key("attTest123", "full")] == ref.remote_url
    assert missing == [ref]


def test_a_mirrored_file_resolves_to_the_local_url(
    mirror: MediaMirror, app_settings: Settings
) -> None:
    ref = attachment_ref(ATTACHMENT, "full")
    assert ref is not None
    path = app_settings.media.directory / "attTest123_full.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not-really-a-png")

    urls, missing = mirror.resolve([ref])

    assert urls[cache_key("attTest123", "full")] == "/media/attTest123_full.png"
    assert missing == []


def test_an_empty_file_is_treated_as_missing(mirror: MediaMirror, app_settings: Settings) -> None:
    ref = attachment_ref(ATTACHMENT, "full")
    assert ref is not None
    path = app_settings.media.directory / "attTest123_full.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")

    urls, missing = mirror.resolve([ref])

    assert urls[cache_key("attTest123", "full")] == ref.remote_url
    assert missing == [ref]
