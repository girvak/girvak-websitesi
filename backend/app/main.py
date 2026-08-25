"""GİRVAK backend — FastAPI app entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import settings
from .db import init_db
from .routers import content, newsletter
from .security import SecurityHeadersMiddleware
from .services.content_source import reload_content


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    refresh_task: asyncio.Task | None = None
    # Pooling-based invalidation:
    # periodically clears backend in-memory caches so the next request
    # pulls fresh Airtable rows.
    # (noop change to force reload when working on content fallbacks)
    if (
        settings.content_source == "airtable"
        and settings.content_cache_enabled
        and settings.content_auto_refresh_seconds > 0
    ):
        async def _auto_invalidate_loop() -> None:
            while True:
                await asyncio.sleep(settings.content_auto_refresh_seconds)
                try:
                    # Only clear caches; avoid Airtable dynamic sync each cycle.
                    reload_content(sync_dynamic=False)
                except Exception:
                    # Never crash the app because of cache invalidation.
                    pass

        refresh_task = asyncio.create_task(_auto_invalidate_loop())
    yield

    if refresh_task:
        refresh_task.cancel()


_docs_url = "/docs" if settings.debug else None
_redoc_url = "/redoc" if settings.debug else None
_openapi_url = "/openapi.json" if settings.debug else None

app = FastAPI(
    title="GİRVAK API",
    description="Content + forms backend for the GİRVAK website.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

if settings.allowed_host_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "If-None-Match", "X-Requested-With", "X-Admin-Token"],
)

app.include_router(content.router)
app.include_router(newsletter.router)

# Mirrored Airtable attachments. Airtable's own attachment URLs expire after a
# few hours, so the static build serves images from here instead — see
# services/media.py. Files are content-addressed by attachment id, so they are
# immutable and safe to cache hard.
settings.media_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    settings.media_url_prefix,
    StaticFiles(directory=settings.media_dir),
    name="media",
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
