"""
Module: girvak/http/router.py
Layer: Router
Purpose: The mount list. One include per module router, plus liveness.
         No path handler for a product noun lives here.

Dependencies: none
Called by: main.py
Calls: modules/*/router.py
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["meta"], summary="Liveness")
def health() -> dict[str, str]:
    """Report that the process is up.

    Touches no database and no cache on purpose: a probe that fails because a
    dependency is briefly slow flaps pods and makes an outage worse.

    Returns:
        A fixed payload.
    """
    return {"status": "ok"}
