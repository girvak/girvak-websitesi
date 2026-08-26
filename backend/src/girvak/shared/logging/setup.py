"""
Module: girvak/shared/logging/setup.py
Layer: Shared
Purpose: Build the one logging pipeline (queue -> listener -> filters -> JSON ->
         stdout) and hand out named loggers. Called once per process.
         A module may only call get_logger.

Dependencies:
    - Settings: log level

Called by: main.py (lifespan), every module that logs
Calls: shared/logging/filters.py, shared/logging/formatter.py, shared/logging/names.py
"""

from __future__ import annotations

import atexit
import logging
import queue
import sys
from logging.handlers import QueueHandler, QueueListener

from girvak.shared.logging.filters import ContextFilter, RedactFilter
from girvak.shared.logging.formatter import JsonFormatter
from girvak.shared.logging.names import LoggerName

_listener: QueueListener | None = None
_log_queue: queue.SimpleQueue[logging.LogRecord] | None = None


def configure_logging(level: str) -> None:
    """Wire the pipeline. Idempotent: a second call changes nothing.

    Args:
        level: Level name for application loggers ("INFO", "DEBUG", ...).
    """
    global _listener, _log_queue

    if _listener is not None:
        return

    _log_queue = queue.SimpleQueue()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JsonFormatter())
    stdout_handler.addFilter(ContextFilter())
    stdout_handler.addFilter(RedactFilter())

    _listener = QueueListener(_log_queue, stdout_handler, respect_handler_level=True)
    _listener.start()
    atexit.register(shutdown_logging)

    queue_handler = QueueHandler(_log_queue)

    # Libraries print through the root logger; keep them on the same pipeline so
    # nothing writes a foreign format to stdout.
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(queue_handler)
    root.setLevel(logging.WARNING)

    for name in LoggerName:
        logger = logging.getLogger(name.value)
        logger.handlers.clear()
        logger.addHandler(queue_handler)
        logger.setLevel(level)
        logger.propagate = False


def shutdown_logging() -> None:
    """Flush and stop the listener thread. Safe to call twice."""
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None


def get_logger(name: LoggerName) -> logging.Logger:
    """Return the logger for a layer.

    Args:
        name: Which layer is logging.

    Returns:
        A configured logger. Call sites use .info / .warning / .error only.
    """
    return logging.getLogger(name.value)
