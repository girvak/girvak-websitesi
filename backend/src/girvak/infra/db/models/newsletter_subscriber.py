"""
Module: girvak/infra/db/models/newsletter_subscriber.py
Layer: Model
Purpose: The one table this product writes: an email address that asked for the
         newsletter. Table and columns only — the subscribe rule is the service.

Dependencies: none
Called by: infra/db/repositories/newsletter_subscriber.py, migrations/env.py
Calls: infra/db/models/base.py
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from girvak.infra.db.models.base import Base, Timestamps, UUIDPrimaryKey


class NewsletterSubscriber(Base, UUIDPrimaryKey, Timestamps):
    """One address on the newsletter list.

    The address is stored normalised (lower-cased, trimmed) so the unique
    constraint is what actually prevents a duplicate.
    """

    __tablename__ = "newsletter_subscribers"

    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
