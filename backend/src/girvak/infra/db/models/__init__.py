"""
Module: girvak/infra/db/models/__init__.py
Layer: Model
Purpose: Import every table so Base.metadata is complete for Alembic
         autogenerate and for the test schema.

Dependencies: none
Called by: migrations/env.py, infra/db/repositories/*
Calls: infra/db/models/*
"""

from girvak.infra.db.models.base import Base
from girvak.infra.db.models.newsletter_subscriber import NewsletterSubscriber

__all__ = ["Base", "NewsletterSubscriber"]
