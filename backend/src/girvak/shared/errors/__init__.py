"""
Module: girvak/shared/errors/__init__.py
Layer: Shared
Purpose: Public surface of the error hierarchy.

Dependencies: none
Called by: modules/*, infra/*, http/errors/
Calls: shared/errors/base.py
"""

from girvak.shared.errors.base import (
    AppBaseError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
)

__all__ = [
    "AppBaseError",
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "NotFoundError",
    "RateLimitError",
    "ServiceUnavailableError",
    "ValidationError",
]
