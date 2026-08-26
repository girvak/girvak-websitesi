"""
Module: girvak/http/errors/handlers.py
Layer: Router
Purpose: The only place an exception becomes HTTP. Four handlers, one body
         shape: {error_code, message, details}. Raise sites never build JSON.

Dependencies: none
Called by: main.py (registration)
Calls: shared/errors/, shared/logging/
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from girvak.shared.errors import AppBaseError, RateLimitError
from girvak.shared.logging import LoggerName, get_logger

_api_logger = get_logger(LoggerName.API)
_error_logger = get_logger(LoggerName.ERROR)

_GENERIC_MESSAGE = "Beklenmeyen bir hata oluştu. Lütfen daha sonra tekrar deneyin."

_FRAMEWORK_CODES = {
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach every error handler to the app.

    Args:
        app: The FastAPI application being built.
    """
    app.add_exception_handler(AppBaseError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_request_validation)
    app.add_exception_handler(StarletteHTTPException, _handle_framework_http)
    app.add_exception_handler(Exception, _handle_unexpected)


def _body(error_code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error_code": error_code, "message": message, "details": details or {}}


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppBaseError)
    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitError):
        headers["Retry-After"] = str(exc.retry_after_seconds)

    if exc.http_status_code >= 500:
        _error_logger.error(
            "request_failed",
            exc_info=True,
            extra={"error_code": exc.error_code, "status_code": exc.http_status_code},
        )
    else:
        _api_logger.warning(
            "request_rejected",
            extra={"error_code": exc.error_code, "status_code": exc.http_status_code},
        )

    return JSONResponse(
        status_code=exc.http_status_code,
        content=_body(exc.error_code, exc.message, exc.details),
        headers=headers,
    )


async def _handle_request_validation(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Field names only. The raw body may carry an email or a token.
    fields = {
        ".".join(str(part) for part in error["loc"][1:]): error["msg"] for error in exc.errors()
    }
    _api_logger.warning(
        "request_rejected",
        extra={"error_code": "VALIDATION_ERROR", "status_code": 422, "fields": list(fields)},
    )
    return JSONResponse(
        status_code=422,
        content=_body("VALIDATION_ERROR", "Gönderilen bilgiler geçersiz.", {"fields": fields}),
    )


async def _handle_framework_http(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    error_code = _FRAMEWORK_CODES.get(exc.status_code, "HTTP_ERROR")
    message = "İstenen adres bulunamadı." if exc.status_code == 404 else str(exc.detail)
    _api_logger.warning(
        "request_rejected",
        extra={"error_code": error_code, "status_code": exc.status_code},
    )
    return JSONResponse(status_code=exc.status_code, content=_body(error_code, message))


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    _error_logger.error(
        "request_failed",
        exc_info=True,
        extra={"error_code": "INTERNAL_ERROR", "status_code": 500},
    )
    return JSONResponse(status_code=500, content=_body("INTERNAL_ERROR", _GENERIC_MESSAGE))
