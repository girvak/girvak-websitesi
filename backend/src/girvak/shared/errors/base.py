"""
Module: girvak/shared/errors/base.py
Layer: Shared
Purpose: The one exception hierarchy this application raises. Each parent fixes
         an HTTP status and a generic error_code; features override the code and
         the user-facing message. No product noun lives here.

Dependencies: none
Called by: modules/*, infra/*, http/errors/handlers.py
Calls: nothing
"""

from __future__ import annotations

from typing import Any


class AppBaseError(Exception):
    """Base for every error this application raises on purpose.

    Args:
        message: User-facing text, in the product language.
        details: Ids and field names the caller may see. Never SQL, secrets,
            file paths, or another visitor's data.
    """

    http_status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class NotFoundError(AppBaseError):
    """The resource does not exist, or the caller may not know that it does."""

    http_status_code = 404
    error_code = "NOT_FOUND"


class AuthenticationError(AppBaseError):
    """No credential, or one that does not verify."""

    http_status_code = 401
    error_code = "UNAUTHENTICATED"


class AuthorizationError(AppBaseError):
    """Authenticated, but not allowed to do this."""

    http_status_code = 403
    error_code = "FORBIDDEN"


class ValidationError(AppBaseError):
    """A business rule rejected the input.

    Not the request-schema failure — FastAPI raises RequestValidationError for
    that, and http/errors maps it separately.
    """

    http_status_code = 422
    error_code = "VALIDATION_ERROR"


class ConflictError(AppBaseError):
    """The write cannot land in the current state (duplicate, illegal transition)."""

    http_status_code = 409
    error_code = "CONFLICT"


class RateLimitError(AppBaseError):
    """The caller exceeded a cap.

    Args:
        message: User-facing text.
        retry_after_seconds: What the Retry-After header should say.
        details: As AppBaseError.
    """

    http_status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"

    def __init__(
        self,
        message: str,
        retry_after_seconds: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.retry_after_seconds = retry_after_seconds


class ServiceUnavailableError(AppBaseError):
    """A system we depend on is down or too slow (database, Airtable, disk)."""

    http_status_code = 503
    error_code = "SERVICE_UNAVAILABLE"
