"""
Module: girvak/infra/db/repositories/newsletter_subscriber.py
Layer: Repository
Purpose: SQL for the newsletter_subscribers table. Flushes; never commits, never
         decides whether a duplicate is an error.

Dependencies:
    - AsyncSession: injected by the service

Called by: modules/newsletter/service.py
Calls: infra/db/models/newsletter_subscriber.py
"""

from __future__ import annotations

from girvak.infra.db.models.newsletter_subscriber import NewsletterSubscriber
from girvak.infra.db.repositories.base import BaseRepository


class NewsletterSubscriberRepository(BaseRepository):
    """Row access for one table."""

    async def create(self, email: str) -> NewsletterSubscriber:
        """Stage a new subscriber row.

        Args:
            email: Already normalised address.

        Returns:
            The flushed row, with its id assigned.

        Raises:
            sqlalchemy.exc.IntegrityError: The address is already on the list.
                The service translates this; the repository does not catch it.
        """
        return await self.add(NewsletterSubscriber(email=email))
