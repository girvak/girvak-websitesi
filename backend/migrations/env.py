"""
Module: migrations/env.py
Layer: Shared
Purpose: Point Alembic at this project's metadata and DSN. Hand-written and
         type-checked; it holds no upgrade logic.

Dependencies:
    - Settings: the DSN
    - Base.metadata: the tables autogenerate compares against

Called by: alembic (upgrade / revision)
Calls: girvak/config, girvak/infra/db/models
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from girvak.config import get_settings
from girvak.infra.db import models  # noqa: F401  # registers every table on Base
from girvak.infra.db.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
# The DSN comes from Settings, unless a caller already supplied one — the test
# suite builds the schema against its own database without an environment.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", get_settings().database.dsn)


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run the chain against the configured database."""
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
