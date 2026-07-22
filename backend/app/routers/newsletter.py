"""Newsletter subscription endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from ..db import add_subscriber
from ..models import NewsletterRequest, NewsletterResponse

router = APIRouter(prefix="/api", tags=["newsletter"])


@router.post("/newsletter", response_model=NewsletterResponse)
def subscribe(payload: NewsletterRequest) -> NewsletterResponse:
    is_new = add_subscriber(payload.email)
    # TODO: forward to Airtable / Mailchimp here when configured.
    return NewsletterResponse(
        status="subscribed" if is_new else "already_subscribed",
        email=payload.email,
    )
