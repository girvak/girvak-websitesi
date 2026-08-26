"""
Module: girvak/http/media.py
Layer: Router
Purpose: Serve mirrored Airtable attachments with immutable cache headers.
         Filenames are content-addressed by attachment id, so a file at a given
         URL never changes. No product noun: this layer does not know what the
         image shows.

Dependencies: none
Called by: main.py (mount)
Calls: nothing
"""

from __future__ import annotations

import os
from typing import Any

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# One year. Safe because the filename carries the Airtable attachment id: a new
# image is a new name, never a new body at the same URL.
_IMMUTABLE = "public, max-age=31536000, immutable"


class ImmutableStaticFiles(StaticFiles):
    """StaticFiles for content-addressed files."""

    def file_response(
        self,
        full_path: str | os.PathLike[Any],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        """Add the immutable cache header to whatever StaticFiles decided.

        Args:
            full_path: Resolved file path.
            stat_result: Its stat, as StaticFiles read it.
            scope: ASGI scope of this request.
            status_code: Status StaticFiles chose.

        Returns:
            The file (or 304) response, with Cache-Control set.
        """
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Cache-Control"] = _IMMUTABLE
        return response
