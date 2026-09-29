"""
Module: girvak/infra/storage/media_mirror.py
Layer: Repository
Purpose: Copy an Airtable attachment to disk once and hand out a URL that never
         expires. Airtable's own attachment links carry an expiry stamp and
         start returning 403 within hours; a page holding one breaks silently.

         Filenames are `<attachment id>_<variant>.<ext>` — the attachment id is
         stable, so a replaced image in Airtable is a new id and a new file.

         Portraits (the `large` rendition of a PNG or JPEG) are stored as WebP.
         They are 512px cut-outs with a transparency channel, which PNG stores
         at about 220 KB and WebP at about 26 KB — the difference between a
         400-person page costing 83 MB of photos and costing 10. Logos (`orig`)
         and anything vector keep their own format. A file that will not convert
         is kept as it arrived, so a bad image never becomes a missing one.

Dependencies:
    - Settings: mirror on/off, directory, URL prefix, timeout
    - Pillow: the WebP conversion

Called by: modules/content/service.py
Calls: nothing
"""

from __future__ import annotations

import asyncio
import ipaddress
import mimetypes
import os
import re
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps

from girvak.config import Settings
from girvak.shared.logging import LoggerName, get_logger

_logger = get_logger(LoggerName.SYSTEM)

_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")
_MAX_BYTES = 10 * 1024 * 1024
_ALLOWED_HOST_SUFFIXES = (".airtableusercontent.com", ".airtable.com")
_ALLOWED_HOSTS = frozenset({"dl.airtable.com", "airtableusercontent.com"})

# Which files become WebP, and how. Only the `large` rendition: that is the
# portrait size; logos ask for `orig` and must keep their exact pixels.
_WEBP_VARIANT = "large"
_WEBP_SOURCE_EXTENSIONS = frozenset({".png", ".jpg"})
_WEBP_QUALITY = 85
# Airtable's `large` is 512px; when it has none the original arrives instead, and
# a 3000px portrait has no business on a card.
_WEBP_MAX_SIDE = 1024


@dataclass(frozen=True)
class AttachmentRef:
    """One attachment, and which rendition of it a page wants."""

    attachment_id: str
    remote_url: str
    filename: str
    content_type: str
    # What the caller asked for ("full", "large", "orig") — the lookup key.
    requested: str
    # What Airtable actually offers, which decides the filename on disk.
    variant: str


class MediaMirror:
    """Disk mirror for attachments, plus the URL map a mapping pass reads."""

    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.media.mirror
        self._directory = settings.media.directory
        self._url_prefix = settings.media.url_prefix.rstrip("/")
        self._timeout = settings.media.download_timeout_seconds
        # Downloads that failed: retried on the next refresh, not on every
        # request — a dead URL would otherwise stall every page render.
        self._failed: set[str] = set()
        # Queued downloads, keyed by target filename, drained by one worker.
        self._pending: dict[str, AttachmentRef] = {}
        self._worker: asyncio.Task[None] | None = None

    def public_url(self, ref: AttachmentRef) -> str | None:
        """Return the local URL when the file is already mirrored.

        Args:
            ref: The attachment and variant.

        Returns:
            A `/media/...` URL, or None when the file is not on disk. A portrait
            not yet converted answers with its PNG until the WebP exists.
        """
        for name in self._names(ref):
            path = self._directory / name
            if path.is_file() and path.stat().st_size > 0:
                return f"{self._url_prefix}/{name}"
        return None

    def resolve(self, refs: list[AttachmentRef]) -> tuple[dict[str, str], list[AttachmentRef]]:
        """Map every attachment to a URL without touching the network.

        Args:
            refs: Every attachment the content pass will need.

        Returns:
            The URL map, and the attachments that are not on disk yet. The map
            holds the local URL where a file exists and the expiring Airtable URL
            where it does not — a short-lived image beats a missing one, and it
            beats making the visitor wait for a download.
        """
        resolved: dict[str, str] = {}
        missing: list[AttachmentRef] = []

        for ref in refs:
            key = cache_key(ref.attachment_id, ref.requested)
            if key in resolved:
                continue
            local = self.public_url(ref) if self._enabled else None
            if local:
                resolved[key] = local
                # A portrait still on disk as PNG is served as it is, and queued
                # so its WebP is made next — from the file, not from Airtable.
                if self._is_unconverted(ref, local) and self._filename(ref) not in self._failed:
                    missing.append(ref)
                continue
            resolved[key] = ref.remote_url
            if self._enabled and self._filename(ref) not in self._failed:
                missing.append(ref)

        return resolved, missing

    def fetch_in_background(self, refs: list[AttachmentRef]) -> None:
        """Queue missing attachments for download, without holding up the request.

        A cold mirror on a base with hundreds of photos is minutes of downloads;
        doing that inside a page render is how a deploy turns into an outage. The
        first render therefore serves Airtable's own URLs, and the next snapshot
        picks up the local copies.

        Work is queued, never dropped: a second page's images must not be skipped
        because the first page's batch is still running.

        Args:
            refs: Attachments that are not on disk yet.
        """
        if not self._enabled:
            return

        for ref in refs:
            name = self._filename(ref)
            if name and name not in self._failed:
                self._pending[name] = ref

        if self._pending and self._worker is None:
            self._worker = asyncio.create_task(self._drain())

    async def _drain(self) -> None:
        """Download everything queued, including whatever arrives while running."""
        try:
            while self._pending:
                batch = list(self._pending.values())
                await self.mirror_all(batch)
                for ref in batch:
                    self._pending.pop(self._filename(ref), None)
        finally:
            self._worker = None

    async def mirror_all(self, refs: list[AttachmentRef]) -> dict[str, str]:
        """Download whatever is missing and map every attachment to a URL.

        Args:
            refs: Every attachment the content pass will need.

        Returns:
            attachment_id + variant -> URL, local where the download succeeded.
        """
        resolved, missing = self.resolve(refs)

        if not missing:
            return resolved

        self._directory.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as http_client:
            semaphore = asyncio.Semaphore(8)

            async def fetch(ref: AttachmentRef) -> tuple[str, str | None]:
                async with semaphore:
                    return cache_key(ref.attachment_id, ref.requested), await self._download(
                        http_client, ref
                    )

            for key, url in await asyncio.gather(*(fetch(ref) for ref in missing)):
                if url:
                    resolved[key] = url

        return resolved

    def reset_failures(self) -> None:
        """Let previously failed downloads be tried again."""
        self._failed.clear()

    @property
    def pending_count(self) -> int:
        """How many downloads are still queued. Read by tests and diagnostics."""
        return len(self._pending)

    async def _download(self, http_client: httpx.AsyncClient, ref: AttachmentRef) -> str | None:
        name = self._filename(ref)
        if name and self._converts(ref):
            converted = await self._convert_existing(ref, name)
            if converted:
                return f"{self._url_prefix}/{name}"
            if (self._directory / self._original_filename(ref)).is_file():
                return None  # kept as it is; the failure is already logged
        if not name or not ref.remote_url or not _host_allowed(ref.remote_url):
            if ref.remote_url:
                _logger.warning("media_host_rejected", extra={"attachment_id": ref.attachment_id})
            return None

        destination = self._directory / name
        # Named for the format it arrives in, not the one it is stored as: the
        # WebP conversion writes its own `.part` beside the target, and the two
        # must never be the same file.
        partial = self._directory / f"{self._original_filename(ref)}.part"

        try:
            written = 0
            with partial.open("wb") as handle:
                async with http_client.stream("GET", ref.remote_url) as response:
                    response.raise_for_status()
                    if not _is_image(response.headers.get("content-type", "")):
                        raise ValueError("unexpected content type")
                    async for chunk in response.aiter_bytes(65536):
                        written += len(chunk)
                        if written > _MAX_BYTES:
                            raise ValueError("attachment too large")
                        handle.write(chunk)
            name = await self._finish(ref, partial, destination)
        except (httpx.HTTPError, ValueError, OSError) as exc:
            self._failed.add(name)
            _logger.warning(
                "media_mirror_failed",
                extra={"attachment_id": ref.attachment_id, "reason": str(exc)},
            )
            partial.unlink(missing_ok=True)
            return None

        return f"{self._url_prefix}/{name}"

    async def _finish(self, ref: AttachmentRef, partial: Path, destination: Path) -> str:
        """Move a downloaded file into place, as WebP when it is a portrait.

        Returns:
            The name it was stored under: the WebP, or — when the image would not
            convert — the original, so the page still gets a picture.
        """
        if not self._converts(ref):
            # Atomic: a reader never sees a half-written file.
            os.replace(partial, destination)
            return destination.name
        try:
            await asyncio.to_thread(_convert_to_webp, partial, destination)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            original = self._directory / self._original_filename(ref)
            os.replace(partial, original)
            _logger.warning(
                "media_convert_failed",
                extra={"attachment_id": ref.attachment_id, "reason": str(exc)},
            )
            return original.name
        await asyncio.to_thread(partial.unlink, missing_ok=True)
        return destination.name

    async def _convert_existing(self, ref: AttachmentRef, name: str) -> bool:
        """Make the WebP from the PNG or JPEG already on disk — no download."""
        original = self._directory / self._original_filename(ref)
        if not original.is_file() or original.stat().st_size == 0:
            return False
        try:
            await asyncio.to_thread(_convert_to_webp, original, self._directory / name)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            self._failed.add(name)
            _logger.warning(
                "media_convert_failed",
                extra={"attachment_id": ref.attachment_id, "reason": str(exc)},
            )
            return False
        return True

    def _converts(self, ref: AttachmentRef) -> bool:
        """Is this attachment stored as WebP?"""
        return ref.requested == _WEBP_VARIANT and _extension(ref) in _WEBP_SOURCE_EXTENSIONS

    def _is_unconverted(self, ref: AttachmentRef, url: str) -> bool:
        return self._converts(ref) and not url.endswith(".webp")

    def _names(self, ref: AttachmentRef) -> list[str]:
        """File names that may hold this attachment, best first."""
        name = self._filename(ref)
        if not name:
            return []
        if self._converts(ref):
            return [name, self._original_filename(ref)]
        return [name]

    def _stem(self, ref: AttachmentRef) -> str:
        attachment_id = _UNSAFE.sub("", ref.attachment_id)
        if not attachment_id:
            return ""
        variant = _UNSAFE.sub("", ref.variant) or "orig"
        return f"{attachment_id}_{variant}"

    def _filename(self, ref: AttachmentRef) -> str:
        stem = self._stem(ref)
        if not stem:
            return ""
        return f"{stem}.webp" if self._converts(ref) else f"{stem}{_extension(ref)}"

    def _original_filename(self, ref: AttachmentRef) -> str:
        """The name a file has in its own format — how mirrors stored it before WebP."""
        stem = self._stem(ref)
        return f"{stem}{_extension(ref)}" if stem else ""


def cache_key(attachment_id: str, requested_variant: str) -> str:
    """Key under which one rendition of one attachment is resolved.

    Args:
        attachment_id: Airtable's stable id.
        requested_variant: What the caller asked for ("full", "large", "orig").
            Keyed on the request, not on what Airtable had, so a mapping pass
            looks up what it asked for without knowing the fallback.

    Returns:
        The lookup key used by the content mapping.
    """
    return f"{attachment_id}:{requested_variant}"


def attachment_ref(attachment: Mapping[str, Any], variant: str) -> AttachmentRef | None:
    """Build a reference for one rendition of an Airtable attachment.

    Args:
        attachment: One entry of a multipleAttachments field.
        variant: "full" or "large" for a thumbnail, "orig" for the original.

    Returns:
        The reference, or None when the attachment has no id or no usable URL.
    """
    attachment_id = str(attachment.get("id") or "")
    if not attachment_id:
        return None

    requested = variant
    remote_url = ""
    if variant != "orig":
        thumbnails = attachment.get("thumbnails")
        if isinstance(thumbnails, dict):
            thumbnail = thumbnails.get(variant)
            if isinstance(thumbnail, dict):
                remote_url = str(thumbnail.get("url") or "")
    if not remote_url:
        remote_url = str(attachment.get("url") or "")
        variant = "orig"
    if not remote_url:
        return None

    return AttachmentRef(
        attachment_id=attachment_id,
        remote_url=remote_url,
        filename=str(attachment.get("filename") or ""),
        content_type=str(attachment.get("type") or ""),
        requested=requested,
        variant=variant,
    )


def _extension(ref: AttachmentRef) -> str:
    extension = Path(ref.filename).suffix.lower()
    if not extension:
        extension = mimetypes.guess_extension(ref.content_type) or ""
    if extension in (".jpe", ".jpeg"):
        extension = ".jpg"
    return _UNSAFE.sub("", extension)


def _convert_to_webp(source: Path, destination: Path) -> None:
    """Write `destination` as WebP from any image Pillow reads.

    Keeps the transparency channel where there is one — portraits are cut-outs —
    and turns a phone photo the right way up. Written beside the target and moved
    into place, like every other file here.

    Raises:
        OSError: The file is not an image Pillow can read.
        ValueError: The image is unusable.
        Image.DecompressionBombError: The pixel count is absurd.
    """
    partial = destination.with_name(f"{destination.name}.part")
    try:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened) or opened
            image.thumbnail((_WEBP_MAX_SIDE, _WEBP_MAX_SIDE))
            has_alpha = image.mode in ("RGBA", "LA") or (
                image.mode == "P" and "transparency" in image.info
            )
            image.convert("RGBA" if has_alpha else "RGB").save(
                partial, "WEBP", quality=_WEBP_QUALITY, method=4
            )
        os.replace(partial, destination)
    finally:
        partial.unlink(missing_ok=True)


def _host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in _ALLOWED_HOSTS or host.endswith(_ALLOWED_HOST_SUFFIXES):
        return not _resolves_to_private_address(host)
    return False


def _resolves_to_private_address(host: str) -> bool:
    """Refuse a name that points inside the network (SSRF guard)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
        ):
            return True
    return False


def _is_image(content_type: str) -> bool:
    return content_type.split(";", 1)[0].strip().lower().startswith("image/")


_mirror: MediaMirror | None = None


def init_mirror(settings: Settings) -> None:
    """Create the process-wide mirror.

    Args:
        settings: Directory, prefix, and whether mirroring is on.
    """
    global _mirror
    if _mirror is None:
        _mirror = MediaMirror(settings)


def dispose_mirror() -> None:
    """Drop the process mirror on shutdown."""
    global _mirror
    _mirror = None


def mirror() -> MediaMirror:
    """Return the process mirror.

    Returns:
        The mirror init_mirror built.

    Raises:
        RuntimeError: init_mirror has not run — a wiring bug.
    """
    if _mirror is None:
        raise RuntimeError("init_mirror() must run in the process lifespan first")
    return _mirror
