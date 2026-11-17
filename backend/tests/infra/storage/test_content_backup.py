"""
Module: tests/infra/storage/test_content_backup.py
Layer: Test
Purpose: The on-disk copy of the last good snapshots: it round-trips, replaces
         the old copy whole, answers "nothing" for a missing key, and refuses a
         key that could point outside its directory.

Dependencies: none
Called by: pytest
Calls: girvak/infra/storage/content_backup.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from girvak.infra.storage.content_backup import ContentBackup


def test_a_saved_snapshot_comes_back(tmp_path: Path) -> None:
    backup = ContentBackup(tmp_path / "nested" / "dir")

    backup.save("programs", b'{"categories": []}')

    assert backup.load("programs") == b'{"categories": []}'


def test_a_new_save_replaces_the_old_copy_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    backup = ContentBackup(tmp_path)
    backup.save("home", b"first")

    backup.save("home", b"second")

    assert backup.load("home") == b"second"
    assert [p.name for p in tmp_path.iterdir()] == ["home.json"]


def test_a_key_with_no_backup_is_none(tmp_path: Path) -> None:
    assert ContentBackup(tmp_path).load("apply") is None


@pytest.mark.parametrize("key", ["../etc/passwd", "a/b", "", "Home", "x" * 80])
def test_a_key_that_is_not_a_plain_word_is_refused(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError, match="not a snapshot key"):
        ContentBackup(tmp_path).save(key, b"x")
