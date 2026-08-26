"""
Module: girvak/infra/cache/snapshot.py
Layer: Repository
Purpose: Hold a computed value for a while. In-process, TTL-bounded, and
         clearable. It stores bytes-with-an-expiry; which key and which TTL are
         the calling module's decisions.

Dependencies:
    - Settings: the TTL

Called by: modules/content/service.py
Calls: nothing
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from girvak.config import Settings


@dataclass
class _Entry:
    value: Any
    stored_at: float


class SnapshotCache:
    """One TTL cache per process.

    Deliberately not Redis: a single API container is what this product runs,
    and a shared counter would buy nothing that the refresh endpoint does not
    already give. Several replicas mean each holds its own snapshot — they
    expire on the same TTL, and a refresh call must reach each of them.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, _Entry] = {}
        self._fallbacks: dict[str, Any] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def get(self, key: str) -> Any | None:
        """Return a stored value while it is still fresh.

        Args:
            key: Cache key chosen by the owning module.

        Returns:
            The value, or None when absent or expired.
        """
        entry = self._entries.get(key)
        if entry is None:
            return None
        if self._ttl <= 0 or time.monotonic() - entry.stored_at >= self._ttl:
            self._entries.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        """Store a value with the current time.

        Args:
            key: Cache key chosen by the owning module.
            value: What to hold.
        """
        if self._ttl <= 0:
            return
        self._entries[key] = _Entry(value=value, stored_at=time.monotonic())

    def set_fallback(self, key: str, value: Any) -> None:
        """Remember the last value that was built successfully.

        It has no expiry: it is what a caller serves when the source is down,
        which beats an empty page.

        Args:
            key: Cache key chosen by the owning module.
            value: The value to keep as the fallback.
        """
        self._fallbacks[key] = value

    def get_fallback(self, key: str) -> Any | None:
        """Return the last successfully built value, however old.

        Args:
            key: Cache key chosen by the owning module.

        Returns:
            The value, or None when nothing was ever built.
        """
        return self._fallbacks.get(key)

    def clear(self) -> None:
        """Drop the fresh entries, so the next read recomputes.

        Fallbacks survive: dropping them would turn a refresh during an outage
        into a blank page.
        """
        self._entries.clear()

    def lock(self, key: str) -> asyncio.Lock:
        """Return the lock guarding one key's rebuild.

        Callers hold it so a cold cache under a burst does one rebuild instead
        of one per waiting request. The lock is per key, not per cache: one
        entry's build may need another entry (the home belt reads the people
        snapshot), and a single lock would deadlock on that.

        Args:
            key: Cache key chosen by the owning module.

        Returns:
            That key's lock.
        """
        return self._locks.setdefault(key, asyncio.Lock())


_cache: SnapshotCache | None = None


def init_cache(settings: Settings) -> None:
    """Create the process-wide snapshot cache.

    Args:
        settings: Source of the TTL.
    """
    global _cache
    if _cache is None:
        _cache = SnapshotCache(settings.content.ttl_seconds)


def dispose_cache() -> None:
    """Drop the process cache on shutdown."""
    global _cache
    _cache = None


def cache() -> SnapshotCache:
    """Return the process snapshot cache.

    Returns:
        The cache init_cache built.

    Raises:
        RuntimeError: init_cache has not run — a wiring bug.
    """
    if _cache is None:
        raise RuntimeError("init_cache() must run in the process lifespan first")
    return _cache
