"""
Module: tests/infra/cache/test_snapshot.py
Layer: Test
Purpose: What the snapshot cache remembers after a value stops being fresh: the
         last good copy is there to hand over when the TTL simply ran out, and is
         withheld after an operator cleared the cache.

Dependencies: none
Called by: pytest
Calls: girvak/infra/cache/snapshot.py
"""

from __future__ import annotations

from girvak.infra.cache.snapshot import SnapshotCache


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _built(clock: _Clock, ttl: int = 600) -> SnapshotCache:
    cache = SnapshotCache(ttl, clock)
    cache.set("page", "copy")
    cache.set_fallback("page", "copy")
    return cache


def test_a_value_is_fresh_until_its_ttl_runs_out() -> None:
    clock = _Clock()
    cache = _built(clock)

    clock.now = 599
    assert cache.get("page") == "copy"
    clock.now = 600
    assert cache.get("page") is None


def test_an_expired_value_is_still_there_to_hand_over() -> None:
    clock = _Clock()
    cache = _built(clock)
    clock.now = 601

    assert cache.get("page") is None
    assert cache.get_stale("page") == "copy"


def test_nothing_is_stale_that_was_never_built() -> None:
    assert SnapshotCache(600, _Clock()).get_stale("page") is None


def test_a_cleared_key_has_nothing_stale_until_it_is_built_again() -> None:
    clock = _Clock()
    cache = _built(clock)

    cache.clear()
    assert cache.get_stale("page") is None
    # The outage safety net is still there for a caller that asks for it.
    assert cache.get_fallback("page") == "copy"

    cache.set("page", "new")
    cache.set_fallback("page", "new")
    clock.now = 601
    assert cache.get_stale("page") == "new"


def test_with_caching_off_there_is_no_such_thing_as_stale() -> None:
    cache = SnapshotCache(0, _Clock())
    cache.set_fallback("page", "copy")

    assert cache.get_stale("page") is None


def test_an_entry_can_carry_a_shorter_life_than_the_cache() -> None:
    clock = _Clock()
    cache = SnapshotCache(600, clock)
    cache.set("page", "copy", ttl=30)

    clock.now = 29
    assert cache.get("page") == "copy"
    clock.now = 30
    assert cache.get("page") is None
