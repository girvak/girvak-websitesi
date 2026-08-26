"""
Module: girvak/modules/newsletter/router.py
Layer: Router
Purpose: The public newsletter URL. Parses the request, calls the service,
         returns the response schema. No rule and no SQL.

Dependencies:
    - SessionDep: request-scoped database session

Called by: http/router.py (mount list)
Calls: modules/newsletter/service.py
"""

from __future__ import annotations

from fastapi import APIRouter, status

from girvak.http.deps import SessionDep
from girvak.modules.newsletter.schemas import (
    NewsletterSubscribeRequest,
    NewsletterSubscribeResponse,
)
from girvak.modules.newsletter.service import NewsletterService

router = APIRouter(prefix="/v1/newsletter", tags=["newsletter"])

_CONFIRMATION = "Teşekkürler! Bültene kaydınız alındı."


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=NewsletterSubscribeResponse,
    summary="Subscribe to the newsletter",
    responses={
        409: {"description": "NEWSLETTER_ALREADY_SUBSCRIBED"},
        422: {"description": "VALIDATION_ERROR"},
        429: {"description": "RATE_LIMIT_EXCEEDED"},
    },
)
async def subscribe(
    payload: NewsletterSubscribeRequest,
    session: SessionDep,
) -> NewsletterSubscribeResponse:
    """Add the posted address to the newsletter list.

    Public route: no identity, rate-limited by the transport layer.
    """
    await NewsletterService(session).subscribe(payload.email)
    return NewsletterSubscribeResponse(message=_CONFIRMATION)
