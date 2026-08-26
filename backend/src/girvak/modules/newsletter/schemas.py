"""
Module: girvak/modules/newsletter/schemas.py
Layer: Schema
Purpose: The HTTP contract of /v1/newsletter. Used by this router only.

Dependencies: none
Called by: modules/newsletter/router.py
Calls: nothing
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class NewsletterSubscribeRequest(BaseModel):
    """What the form posts."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)


class NewsletterSubscribeResponse(BaseModel):
    """What the form shows afterwards."""

    message: str
