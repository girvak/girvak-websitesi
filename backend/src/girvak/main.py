"""
Module: girvak/main.py
Layer: Router
Purpose: Build the HTTP application: settings, logging, pools, middleware order,
         error handlers, the mount list, and the media mirror. No route handler
         and no business rule lives here.

Dependencies:
    - Settings: everything this process is allowed to know

Called by: uvicorn (girvak.main:create_app --factory), tests/conftest.py
Calls: config/, shared/logging/, infra/db/session.py, http/*
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from girvak.config import Settings, get_settings
from girvak.http.errors import register_exception_handlers
from girvak.http.media import ImmutableStaticFiles
from girvak.http.middleware.rate_limit import RateLimitMiddleware
from girvak.http.middleware.request_id import RequestIdMiddleware
from girvak.http.middleware.security_headers import SecurityHeadersMiddleware
from girvak.http.router import router as mount_list
from girvak.infra.airtable.client import dispose_client, init_client
from girvak.infra.cache.snapshot import dispose_cache, init_cache
from girvak.infra.db.session import dispose_engine, init_engine
from girvak.infra.storage.media_mirror import dispose_mirror, init_mirror
from girvak.modules.content.router import router as content_router
from girvak.modules.newsletter.router import router as newsletter_router
from girvak.shared.logging import LoggerName, configure_logging, get_logger, shutdown_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open and close everything that lives as long as the process.

    Args:
        app: The application being started.

    Yields:
        Control, while the process serves traffic.
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings)
    init_cache(settings)
    init_mirror(settings)
    init_client(settings)

    get_logger(LoggerName.SYSTEM).info(
        "api_started",
        extra={"environment": settings.environment, "content_source": settings.content.source},
    )
    try:
        yield
    finally:
        await dispose_client()
        await dispose_engine()
        dispose_cache()
        dispose_mirror()
        shutdown_logging()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Wire the application.

    Args:
        settings: Injected in tests. Production reads the environment.

    Returns:
        The configured FastAPI app.

    Raises:
        pydantic.ValidationError: A required setting is missing. The boot must
            die here rather than serve with defaults.
    """
    config = settings or get_settings()

    app = FastAPI(
        title="GİRVAK API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if config.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.docs_enabled else None,
    )

    # Added innermost first: Starlette treats the last registration as outermost.
    # Outside -> inside: trusted host, request id, security headers, CORS,
    # rate limit, routes.
    app.add_middleware(RateLimitMiddleware, settings=config)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "If-None-Match", "X-Admin-Token"],
        expose_headers=["ETag", "X-Request-ID"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    if config.trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.trusted_hosts)

    register_exception_handlers(app)
    app.include_router(mount_list)
    app.include_router(content_router)
    app.include_router(newsletter_router)

    media_dir = config.media.directory
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        config.media.url_prefix,
        ImmutableStaticFiles(directory=media_dir),
        name="media",
    )

    return app
