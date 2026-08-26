"""
Module: girvak/infra/db/repositories/base.py
Layer: Repository
Purpose: The two lines every concrete repository would otherwise copy: hold the
         session, add-and-flush so the primary key exists before commit.
         Deliberately not a generic CRUD framework.

Dependencies:
    - AsyncSession: injected by the service

Called by: infra/db/repositories/*
Calls: nothing
"""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from girvak.infra.db.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository:
    """Session holder for one model's SQL. Never commits."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, instance: ModelT) -> ModelT:
        """Stage a new row and assign its primary key.

        Args:
            instance: The model to persist.

        Returns:
            The same instance, now flushed.
        """
        self._session.add(instance)
        await self._session.flush()
        return instance
