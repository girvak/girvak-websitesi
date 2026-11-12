"""
Module: girvak/infra/storage/content_backup.py
Layer: Repository
Purpose: Keep the last good copy of every page's content on disk, so a restart
         or a long Airtable outage does not drop the site back to the repo's
         old seed (or to an empty page where there is no seed). One JSON file
         per snapshot key. A file is written to a temporary name and renamed
         over the old one, so a crash mid-write never leaves half a file, and
         a file that cannot be read or no longer matches the schema is simply
         treated as no backup. It holds bytes; what they mean is the caller's.

Dependencies:
    - Settings: the directory

Called by: modules/content/service.py
Calls: nothing
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from girvak.config import Settings
from girvak.shared.logging import LoggerName, get_logger

_logger = get_logger(LoggerName.SYSTEM)

_SAFE_KEY = re.compile(r"^[a-z0-9_-]{1,64}$")


class ContentBackup:
    """The last good snapshot of each page, as files in one directory."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, key: str, data: bytes) -> None:
        """Replace one key's backup, atomically.

        Args:
            key: The snapshot key (`home`, `programs`, …).
            data: The serialised snapshot.

        Raises:
            ValueError: The key is not a plain lowercase word.
        """
        target = self._path(key)
        self._directory.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)

    def load(self, key: str) -> bytes | None:
        """One key's backup, or None when there is none or it cannot be read."""
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            return None
        except OSError as exc:
            _logger.warning("content_backup_unreadable", extra={"page": key, "reason": str(exc)})
            return None

    def _path(self, key: str) -> Path:
        if not _SAFE_KEY.match(key):
            raise ValueError(f"not a snapshot key: {key!r}")
        return self._directory / f"{key}.json"


def build_backup(settings: Settings) -> ContentBackup | None:
    """The backup store, or None when backups are switched off."""
    if not settings.content.backup:
        return None
    return ContentBackup(settings.content.backup_directory)
