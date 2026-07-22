"""Tiny SQLite layer for newsletter subscribers.

Kept deliberately dependency-free (stdlib sqlite3). Swap for Postgres/an ORM
later without touching the router — only these three functions are public.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from .config import settings


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscribers (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


def add_subscriber(email: str) -> bool:
    """Insert a subscriber. Returns True if newly added, False if already present."""
    normalized = email.strip().lower()
    with closing(_connect()) as conn:
        try:
            conn.execute("INSERT INTO subscribers (email) VALUES (?)", (normalized,))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
