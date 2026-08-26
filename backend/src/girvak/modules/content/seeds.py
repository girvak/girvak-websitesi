"""
Module: girvak/modules/content/seeds.py
Layer: Service
Purpose: The committed copy of every page. It is what the site serves before
         Airtable is configured, and what a missing fragment falls back to, so
         the site never renders an empty band.

Dependencies: none
Called by: modules/content/service.py
Calls: modules/content/schemas.py
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from girvak.modules.content.schemas import AboutContent, FellowContent, HomeContent

_DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=1)
def home() -> HomeContent:
    """The shipped home page.

    Returns:
        Seed content, parsed once per process.
    """
    return HomeContent.model_validate(_read("home.json"))


@lru_cache(maxsize=1)
def about() -> AboutContent:
    """The shipped about page.

    Returns:
        Seed content, parsed once per process.
    """
    return AboutContent.model_validate(_read("about.json"))


@lru_cache(maxsize=1)
def fellow() -> FellowContent:
    """The shipped fellow-program page.

    Returns:
        Seed content, parsed once per process.
    """
    return FellowContent.model_validate(_read("fellow.json"))


def _read(name: str) -> object:
    with (_DATA_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)
