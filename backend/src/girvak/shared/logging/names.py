"""
Module: girvak/shared/logging/names.py
Layer: Shared
Purpose: The closed set of logger names. A name is a label on one pipeline,
         never a second logging stack.

Dependencies: none
Called by: every call site that logs
Calls: nothing
"""

from __future__ import annotations

from enum import StrEnum


class LoggerName(StrEnum):
    """Which layer a log line came from."""

    API = "api"
    SYSTEM = "system"
    ERROR = "error"
    AUDIT = "audit"
