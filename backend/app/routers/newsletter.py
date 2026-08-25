"""Newsletter subscription endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db import add_subscriber
from ..models import NewsletterRequest, NewsletterResponse
from ..security import newsletter_limiter, require_ajax

router = APIRouter(prefix="/api", tags=["newsletter"])


@router.post(
    "/newsletter",
    response_model=NewsletterResponse,
    dependencies=[Depends(require_ajax), Depends(newsletter_limiter.dependency())],
)
def subscribe(payload: NewsletterRequest) -> NewsletterResponse:
    add_subscriber(payload.email)
    # TODO: forward to Airtable / Mailchimp here when configured.
    # Always return the same status to prevent email enumeration.
    return NewsletterResponse(status="subscribed", email=payload.email)
