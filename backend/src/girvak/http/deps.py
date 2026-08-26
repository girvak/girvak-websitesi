"""
Module: girvak/http/deps.py
Layer: Router
Purpose: What every route may need from the transport layer: a database session,
         and the operator check that guards the cache-refresh call. No product
         rule, no service construction.

Dependencies:
    - Settings: the admin token to compare against

Called by: modules/*/router.py
Calls: infra/db/session.py, config/
"""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from girvak.config import Settings, get_settings
from girvak.infra.db.session import session_scope
from girvak.shared.errors import AuthenticationError

ADMIN_HEADER = "X-Admin-Token"


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one session for this request.

    Yields:
        The session the service and its repositories share. Rolled back on an
        exception and always closed; the service does the committing.
    """
    async with session_scope() as session:
        yield session


def require_admin(
    settings: Annotated[Settings, Depends(get_settings)],
    x_admin_token: Annotated[str | None, Header(alias=ADMIN_HEADER)] = None,
) -> None:
    """Allow the request only when it carries the operator token.

    Args:
        settings: Holds the expected token.
        x_admin_token: Value of the X-Admin-Token header.

    Raises:
        AuthenticationError: Header missing or not equal to the configured token.
    """
    expected = settings.admin_api_key.get_secret_value()
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise AuthenticationError("Bu işlem için geçerli bir yönetici anahtarı gerekiyor.")


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
