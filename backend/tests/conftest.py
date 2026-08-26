"""
Module: tests/conftest.py
Layer: Test
Purpose: Settings built from explicit values (never the developer's shell), the
         wired app, and an HTTP client that speaks to it in-process.

Dependencies: none
Called by: pytest
Calls: girvak/main.py, girvak/config/settings.py
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from girvak.config import Settings, get_settings
from girvak.config.settings import BACKEND_DIR
from girvak.http.deps import get_session
from girvak.infra.cache.snapshot import dispose_cache, init_cache
from girvak.infra.storage.media_mirror import dispose_mirror, init_mirror
from girvak.main import create_app

ADMIN_TOKEN = "test-admin-token"


@pytest.fixture
def settings() -> Iterator[Settings]:
    """Explicit test settings, with the environment ignored."""
    get_settings.cache_clear()
    yield Settings(
        _env_file=None,  # type: ignore[call-arg]
        environment="ci",
        log_level="WARNING",
        docs_enabled=False,
        cors_origins=["http://localhost:4321"],
        trusted_hosts=["testserver", "localhost"],
        admin_api_key=ADMIN_TOKEN,  # type: ignore[arg-type]
        database={"dsn": "postgresql+asyncpg://girvak:girvak@127.0.0.1:5432/girvak_test"},  # type: ignore[arg-type]
    )
    get_settings.cache_clear()


@pytest.fixture
def app_settings(settings: Settings, tmp_path_factory: pytest.TempPathFactory) -> Settings:
    """Test settings with a throwaway media directory."""
    media_dir = tmp_path_factory.mktemp("media")
    return settings.model_copy(
        update={"media": settings.media.model_copy(update={"dir_path": str(media_dir)})}
    )


@pytest.fixture
def app(app_settings: Settings) -> Iterator[FastAPI]:
    """The application, wired the way the lifespan wires it.

    The in-process cache and media mirror are opened here because the ASGI
    transport the tests use does not run the lifespan.
    """
    init_cache(app_settings)
    init_mirror(app_settings)
    application = create_app(app_settings)
    application.dependency_overrides[get_settings] = lambda: app_settings
    yield application
    dispose_cache()
    dispose_mirror()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """In-process HTTP client. Hits real middleware, routers, and handlers."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as async_client:
        yield async_client


# --- PostgreSQL fixtures (tests marked `db`) ---------------------------------
# The schema is built by the revision chain, never by metadata.create_all, so a
# broken migration fails here instead of in production.


@pytest.fixture(scope="session")
def db_dsn() -> str:
    """DSN of the test database.

    Returns:
        The value of TEST_DATABASE_DSN, or the local default.
    """
    return os.getenv(
        "TEST_DATABASE_DSN",
        "postgresql+asyncpg://girvak:girvak@127.0.0.1:5432/girvak_test",
    )


@pytest.fixture(scope="session")
def migrated_db(db_dsn: str) -> str:
    """Run the revision chain once per test session.

    Args:
        db_dsn: Where to build the schema.

    Returns:
        The same DSN, now migrated to head.
    """
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", db_dsn)
    command.upgrade(config, "head")
    return db_dsn


@pytest_asyncio.fixture
async def db_session(migrated_db: str) -> AsyncIterator[AsyncSession]:
    """A session inside an outer transaction that is rolled back at teardown.

    The service under test commits; joining as a savepoint is what makes that
    commit undoable, so one test never leaks rows into the next.
    """
    engine = create_async_engine(migrated_db)
    try:
        async with engine.connect() as connection:
            await connection.begin()
            factory = async_sessionmaker(
                bind=connection,
                expire_on_commit=False,
                autoflush=False,
                join_transaction_mode="create_savepoint",
            )
            async with factory() as session:
                yield session
            await connection.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_client(app: FastAPI, db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTP client whose routes run against the test session."""
    app.dependency_overrides[get_session] = lambda: db_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as async_client:
        yield async_client
    app.dependency_overrides.pop(get_session, None)
