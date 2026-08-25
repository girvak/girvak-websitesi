"""Local mirror for Airtable attachments.

Airtable hands out *expiring* attachment URLs (`v5.airtableusercontent.com/...`
carries an expiry stamp in the path). A few hours after they are issued they
start returning 403. Our Astro build is static, so those URLs get baked into
the HTML — which means every image on the site breaks the next morning even
though the API itself is perfectly healthy.

Fix: copy each attachment to disk the first time we see it, keyed by its
*stable* Airtable attachment id, and hand out `/media/<id>_<variant>.<ext>`
instead. Those URLs never expire, so a build stays valid until the content
actually changes. Replacing a file in Airtable mints a new attachment id, so
the mirror picks the new image up on the next content pull.

Cost is paid once per attachment: afterwards `mirror()` is a stat() call.
A failed download degrades to the raw Airtable URL — a short-lived image
beats a missing one.
"""
from __future__ import annotations

import ipaddress
import logging
import mimetypes
import os
import re
import socket
import threading
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

# Per-filename locks so two concurrent requests don't download the same file.
_LOCKS_GUARD = threading.Lock()
_LOCKS: Dict[str, threading.Lock] = {}

# Attachments whose download failed — retried on the next reload_content(),
# not on every single request (a dead URL would stall each page render).
_FAILED: set = set()

_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")
_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB per attachment

# Hostnames Airtable uses for attachment downloads.
_ALLOWED_HOSTS = frozenset(
    {
        "dl.airtable.com",
        "v5.airtableusercontent.com",
        "airtableusercontent.com",
    }
)


def _lock_for(name: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(name)
        if lock is None:
            lock = _LOCKS[name] = threading.Lock()
        return lock


def _extension(att: Dict[str, Any]) -> str:
    """File extension from the Airtable filename, falling back to the MIME type."""
    ext = Path(str(att.get("filename") or "")).suffix.lower()
    if not ext:
        ext = mimetypes.guess_extension(str(att.get("type") or "")) or ""
    if ext in (".jpe", ".jpeg"):
        ext = ".jpg"
    return _UNSAFE.sub("", ext)


def _filename(att: Dict[str, Any], variant: str) -> str:
    """`<attachment id>_<variant>.<ext>` — thumbnails share the parent's id."""
    att_id = _UNSAFE.sub("", str(att.get("id") or ""))
    return f"{att_id}_{_UNSAFE.sub('', variant)}{_extension(att)}"


def _host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in _ALLOWED_HOSTS or host.endswith(".airtableusercontent.com"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            addr = info[4][0]
            ip = ipaddress.ip_address(addr)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
    except OSError:
        return False
    return host.endswith(".airtable.com")


def _content_type_ok(content_type: str) -> bool:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    return mime.startswith("image/")


def mirror(att: Dict[str, Any], remote_url: str, variant: str) -> str:
    """Return a non-expiring local URL for `remote_url`, downloading it once.

    Falls back to `remote_url` when mirroring is off, the attachment has no id,
    or the download fails.
    """
    if not settings.media_mirror or not remote_url:
        return remote_url
    if not att.get("id"):
        return remote_url
    if not _host_allowed(remote_url):
        logger.warning("[media] rejected download host for attachment %s", att.get("id"))
        return remote_url

    name = _filename(att, variant)
    dest = settings.media_dir / name
    public_url = f"{settings.media_url_prefix}/{name}"

    if dest.is_file() and dest.stat().st_size > 0:
        return public_url
    if name in _FAILED:
        return remote_url

    with _lock_for(name):
        # Another thread may have finished while we waited.
        if dest.is_file() and dest.stat().st_size > 0:
            return public_url

        tmp: Optional[Path] = None
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            total = 0
            with httpx.stream(
                "GET", remote_url, timeout=60.0, follow_redirects=True
            ) as resp:
                resp.raise_for_status()
                if not _content_type_ok(resp.headers.get("content-type", "")):
                    raise ValueError("unexpected content type")
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_bytes(65536):
                        total += len(chunk)
                        if total > _MAX_BYTES:
                            raise ValueError("attachment too large")
                        fh.write(chunk)
            os.replace(tmp, dest)  # atomic — readers never see a partial file
            return public_url
        except Exception as exc:
            _FAILED.add(name)
            logger.warning("[media] mirror failed for %s: %s", name, exc)
            if tmp is not None:
                try:
                    tmp.unlink()
                except OSError:
                    pass
            return remote_url


def reset_failures() -> None:
    """Let previously failed downloads be retried (called on content reload)."""
    _FAILED.clear()


def stats() -> Dict[str, Any]:
    """Mirror size — surfaced by /api/content/publish-guide for debugging."""
    directory = settings.media_dir
    if not directory.is_dir():
        return {"enabled": settings.media_mirror, "files": 0, "bytes": 0}
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix != ".part"]
    return {
        "enabled": settings.media_mirror,
        "files": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "failed": len(_FAILED),
    }
