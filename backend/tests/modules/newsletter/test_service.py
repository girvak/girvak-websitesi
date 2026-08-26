"""
Module: tests/modules/newsletter/test_service.py
Layer: Test
Purpose: The subscribe rule against a real database: one row, normalisation, and
         a duplicate that becomes a typed conflict instead of a second row.

Dependencies: none
Called by: pytest
Calls: girvak/modules/newsletter/service.py
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from girvak.infra.db.models.newsletter_subscriber import NewsletterSubscriber
from girvak.modules.newsletter.service import AlreadySubscribedError, NewsletterService

pytestmark = pytest.mark.db


async def test_subscribe_new_address_stores_one_row(db_session: AsyncSession) -> None:
    await NewsletterService(db_session).subscribe("Yeni.Abone@Example.com")

    stored = (await db_session.execute(select(NewsletterSubscriber.email))).scalars().all()
    assert stored == ["yeni.abone@example.com"]


async def test_subscribe_trims_and_lowercases_before_storing(db_session: AsyncSession) -> None:
    await NewsletterService(db_session).subscribe("  Bulten@Example.COM ")

    stored = (await db_session.execute(select(NewsletterSubscriber.email))).scalars().one()
    assert stored == "bulten@example.com"


async def test_subscribe_same_address_twice_raises_conflict(db_session: AsyncSession) -> None:
    service = NewsletterService(db_session)
    await service.subscribe("abone@example.com")

    with pytest.raises(AlreadySubscribedError):
        await service.subscribe("ABONE@example.com")


async def test_duplicate_attempt_leaves_a_single_row(db_session: AsyncSession) -> None:
    service = NewsletterService(db_session)
    await service.subscribe("abone@example.com")

    with pytest.raises(AlreadySubscribedError):
        await service.subscribe("abone@example.com")

    count = (
        await db_session.execute(select(func.count()).select_from(NewsletterSubscriber))
    ).scalar_one()
    assert count == 1
