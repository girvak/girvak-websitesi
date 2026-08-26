"""
Module: girvak/modules/newsletter/service.py
Layer: Service
Purpose: Subscribing an address to the newsletter: normalise it, store it once,
         and treat a second attempt as a conflict rather than a second row.
         Sending anything to that address does not happen here.

Dependencies:
    - AsyncSession: unit of work for this request
    - NewsletterSubscriberRepository: row access

Called by: modules/newsletter/router.py
Calls: infra/db/repositories/newsletter_subscriber.py
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from girvak.infra.db.repositories.newsletter_subscriber import NewsletterSubscriberRepository
from girvak.shared.errors import ConflictError
from girvak.shared.logging import LoggerName, get_logger

_logger = get_logger(LoggerName.SYSTEM)
_audit = get_logger(LoggerName.AUDIT)


class AlreadySubscribedError(ConflictError):
    """This address is already on the list."""

    error_code = "NEWSLETTER_ALREADY_SUBSCRIBED"

    def __init__(self) -> None:
        super().__init__("Bu e-posta adresi bültene zaten kayıtlı.")


class NewsletterService:
    """The newsletter list, as the product sees it."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._subscribers = NewsletterSubscriberRepository(session)

    async def subscribe(self, email: str) -> None:
        """Add an address to the list.

        Args:
            email: Address as the visitor typed it.

        Raises:
            AlreadySubscribedError: The address is already stored. The unique
                constraint decides this, not a prior SELECT — two simultaneous
                submissions would both pass a check.
        """
        normalised = email.strip().lower()

        try:
            await self._subscribers.create(normalised)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise AlreadySubscribedError() from None

        _audit.info("newsletter_subscribed", extra={"resource": "newsletter_subscriber"})
        _logger.info("newsletter_subscribe_stored")
