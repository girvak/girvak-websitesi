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
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from girvak.config import Settings


@dataclass
class _Entry:
    value: Any
    stored_at: float
    # This entry's own lifetime; None means the cache's.
    ttl: float | None = None


class SnapshotCache:
    """One TTL cache per process.

    Deliberately not Redis: a single API container is what this product runs,
    and a shared counter would buy nothing that the refresh endpoint does not
    already give. Several replicas mean each holds its own snapshot — they
    expire on the same TTL, and a refresh call must reach each of them.
    """

    def __init__(self, ttl_seconds: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        # Injected so a test can move time; patching `time.monotonic` itself
        # would move the event loop's clock too.
        self._clock = clock
        self._entries: dict[str, _Entry] = {}
        self._fallbacks: dict[str, Any] = {}
        # Keys an operator cleared. Their fallback is an outage safety net, not
        # something to hand out while the source is healthy.
        self._cleared: set[str] = set()
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
        lifetime = self._ttl if entry.ttl is None else entry.ttl
        if self._ttl <= 0 or self._clock() - entry.stored_at >= lifetime:
            self._entries.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value with the current time.

        Args:
            key: Cache key chosen by the owning module.
            value: What to hold.
            ttl: How long this one entry is fresh, in seconds; the cache's own
                TTL when omitted. A shorter one is how a caller retries soon
                after a failure instead of a full TTL later.
        """
        if self._ttl <= 0:
            return
        self._entries[key] = _Entry(value=value, stored_at=self._clock(), ttl=ttl)
        self._cleared.discard(key)

    def get_stale(self, key: str) -> Any | None:
        """Return the last built value when its TTL simply ran out.

        This is what lets a caller answer at once and rebuild behind the
        request. It answers only for a natural expiry: after `clear` the
        operator wants what Airtable holds now, so there is nothing stale to
        hand out. With caching off (TTL 0) there is no such thing as stale.

        Args:
            key: Cache key chosen by the owning module.

        Returns:
            The last good value, or None when there is none or it was cleared.
        """
        if self._ttl <= 0 or key in self._cleared:
            return None
        return self._fallbacks.get(key)

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
        into a blank page. They are marked, though, so `get_stale` does not hand
        one out as an answer while the source is healthy.
        """
        self._entries.clear()
        self._cleared.update(self._fallbacks)

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
