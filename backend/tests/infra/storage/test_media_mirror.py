"""
Module: tests/infra/storage/test_media_mirror.py
Layer: Test
Purpose: What the mirror answers before anything is downloaded, the filename
         scheme that makes a mirrored file cacheable forever, and which files are
         stored as WebP (portraits) and which keep their own format.

Dependencies: none
Called by: pytest
Calls: girvak/infra/storage/media_mirror.py
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from PIL import Image

from girvak.config import Settings
from girvak.infra.storage import media_mirror
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


# --- WebP portraits -----------------------------------------------------------


def _write_png(path: Path, size: tuple[int, int] = (64, 48)) -> bytes:
    """A cut-out: opaque in the middle, fully transparent at the corner."""
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    for x in range(size[0] // 4, size[0] * 3 // 4):
        for y in range(size[1] // 4, size[1] * 3 // 4):
            image.putpixel((x, y), (200, 40, 40, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")
    return path.read_bytes()


def _http(body: bytes, content_type: str = "image/png") -> httpx.AsyncClient:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": content_type})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _airtable_hosts_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The host guard resolves DNS; these tests are about what happens after it."""
    monkeypatch.setattr(media_mirror, "_host_allowed", lambda url: True)


@pytest.mark.asyncio
async def test_a_large_png_is_stored_as_webp_and_keeps_its_transparency(
    mirror: MediaMirror, app_settings: Settings, tmp_path: Path
) -> None:
    ref = attachment_ref(ATTACHMENT, "large")
    assert ref is not None
    source = _write_png(tmp_path / "in.png")

    async with _http(source) as http:
        url = await mirror._download(http, ref)

    directory = app_settings.media.directory
    assert url == "/media/attTest123_large.webp"
    with Image.open(directory / "attTest123_large.webp") as stored:
        assert stored.format == "WEBP"
        assert stored.mode == "RGBA"
        assert stored.getpixel((0, 0))[3] == 0  # the corner is still transparent
        assert stored.getpixel((32, 24))[3] == 255
    assert not (directory / "attTest123_large.png").exists()
    assert list(directory.glob("*.part")) == []


@pytest.mark.asyncio
async def test_logos_keep_their_exact_bytes(
    mirror: MediaMirror, app_settings: Settings, tmp_path: Path
) -> None:
    ref = attachment_ref(ATTACHMENT, "orig")
    assert ref is not None
    source = _write_png(tmp_path / "logo.png")

    async with _http(source) as http:
        url = await mirror._download(http, ref)

    assert url == "/media/attTest123_orig.png"
    assert (app_settings.media.directory / "attTest123_orig.png").read_bytes() == source


@pytest.mark.asyncio
async def test_a_vector_is_never_converted(mirror: MediaMirror, app_settings: Settings) -> None:
    svg = {**ATTACHMENT, "filename": "mark.svg", "type": "image/svg+xml", "thumbnails": {}}
    ref = attachment_ref(svg, "large")
    assert ref is not None
    body = b"<svg xmlns='http://www.w3.org/2000/svg'/>"

    async with _http(body, "image/svg+xml") as http:
        url = await mirror._download(http, ref)

    assert url == "/media/attTest123_orig.svg"
    assert (app_settings.media.directory / "attTest123_orig.svg").read_bytes() == body


@pytest.mark.asyncio
async def test_an_oversized_original_is_scaled_down(
    mirror: MediaMirror, app_settings: Settings, tmp_path: Path
) -> None:
    # No `large` thumbnail: the 2000px original arrives instead.
    ref = attachment_ref({**ATTACHMENT, "thumbnails": {}}, "large")
    assert ref is not None
    source = _write_png(tmp_path / "big.png", size=(2000, 1500))

    async with _http(source) as http:
        await mirror._download(http, ref)

    with Image.open(app_settings.media.directory / "attTest123_orig.webp") as stored:
        assert max(stored.size) == 1024


@pytest.mark.asyncio
async def test_an_existing_png_is_converted_from_disk_with_no_download(
    mirror: MediaMirror, app_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref = attachment_ref(ATTACHMENT, "large")
    assert ref is not None
    directory = app_settings.media.directory
    _write_png(directory / "attTest123_large.png")

    # Before: served as the PNG, and queued so its WebP gets made.
    urls, missing = mirror.resolve([ref])
    assert urls[cache_key("attTest123", "large")] == "/media/attTest123_large.png"
    assert missing == [ref]

    def no_network(*_: object, **__: object) -> None:
        raise AssertionError("converting a file already on disk must not download it")

    monkeypatch.setattr(httpx.AsyncClient, "stream", no_network)
    converted = await mirror.mirror_all([ref])

    assert converted[cache_key("attTest123", "large")] == "/media/attTest123_large.webp"
    # After: the WebP wins, nothing is left to do, and the PNG is not deleted —
    # a page cached in a browser may still point at it.
    urls, missing = mirror.resolve([ref])
    assert urls[cache_key("attTest123", "large")] == "/media/attTest123_large.webp"
    assert missing == []
    assert (directory / "attTest123_large.png").is_file()


def test_the_webp_is_preferred_when_both_exist(mirror: MediaMirror, app_settings: Settings) -> None:
    ref = attachment_ref(ATTACHMENT, "large")
    assert ref is not None
    directory = app_settings.media.directory
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "attTest123_large.png").write_bytes(b"png")
    (directory / "attTest123_large.webp").write_bytes(b"webp")

    assert mirror.public_url(ref) == "/media/attTest123_large.webp"


@pytest.mark.asyncio
async def test_an_image_that_will_not_convert_is_kept_as_it_arrived(
    mirror: MediaMirror, app_settings: Settings
) -> None:
    ref = attachment_ref(ATTACHMENT, "large")
    assert ref is not None
    body = b"this is not an image at all"

    async with _http(body) as http:
        url = await mirror._download(http, ref)

    # A picture that will not convert is still a picture the page can try.
    assert url == "/media/attTest123_large.png"
    assert (app_settings.media.directory / "attTest123_large.png").read_bytes() == body

    # The next pass tries the local file once, gives up, and stops asking.
    await mirror.mirror_all([ref])
    _, missing = mirror.resolve([ref])
    assert missing == []
