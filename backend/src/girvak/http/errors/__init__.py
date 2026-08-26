"""
Module: girvak/http/errors/__init__.py
Layer: Router
Purpose: Public surface of the HTTP error map.

Dependencies: none
Called by: main.py
Calls: http/errors/handlers.py
"""

from girvak.http.errors.handlers import register_exception_handlers

__all__ = ["register_exception_handlers"]
