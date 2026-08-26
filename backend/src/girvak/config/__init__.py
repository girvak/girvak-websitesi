"""
Module: girvak/config/__init__.py
Layer: Shared
Purpose: Public surface of the settings package.

Dependencies: none
Called by: main.py, http/, modules/, infra/, migrations/env.py
Calls: config/settings.py
"""

from girvak.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
