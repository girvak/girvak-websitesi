"""
Module: girvak/shared/logging/__init__.py
Layer: Shared
Purpose: Public surface of the logging package.

Dependencies: none
Called by: main.py, http/, modules/, infra/
Calls: shared/logging/setup.py, shared/logging/names.py, shared/logging/context.py
"""

from girvak.shared.logging.context import bind_request_id, request_id_var, reset_request_id
from girvak.shared.logging.names import LoggerName
from girvak.shared.logging.setup import configure_logging, get_logger, shutdown_logging

__all__ = [
    "LoggerName",
    "bind_request_id",
    "configure_logging",
    "get_logger",
    "request_id_var",
    "reset_request_id",
    "shutdown_logging",
]
