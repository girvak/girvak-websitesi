"""
Module: girvak/infra/db/session.py
Layer: Repository
Purpose: The one async engine, its pool, and the session scope every request and
         job runs inside. Opens and closes sessions; it never commits — the
         service owns the transaction.

Dependencies:
    - Settings: DSN, pool size, statement timeout

Called by: main.py (lifespan), http/deps.py
Calls: nothing
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from girvak.config import Settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> None:
    """Create the process-wide engine and session factory.

    Args:
        settings: Source of the DSN and every pool/timeout number.
    """
    global _engine, _session_factory

    if _engine is not None:
        return

    _engine = create_async_engine(
        settings.database.dsn,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_pre_ping=True,
        connect_args={
            # asyncpg applies this at connect time; a query with no ceiling would
            # hold a pool slot forever.
            "server_settings": {
                "statement_timeout": str(settings.database.statement_timeout_ms),
            }
        },
    )
    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,
        autoflush=False,
    )


async def dispose_engine() -> None:
    """Close the pool on process shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process session factory.

    Returns:
        The factory init_engine built.

    Raises:
        RuntimeError: init_engine has not run. That is a wiring bug, not a
            runtime condition.
    """
    if _session_factory is None:
        raise RuntimeError("init_engine() must run in the process lifespan first")
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Open one session for one use case.

    Rolls back if the caller raised, and always closes so the connection returns
    to the pool. Committing is the service's job.

    Yields:
        The session the service and its repositories share.
    """
    async with session_factory()() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
