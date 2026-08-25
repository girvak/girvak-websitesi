"""Application configuration, loaded from environment / .env."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # CORS — frontend origins allowed to call this API.
    cors_origins: str = "http://localhost:4321,http://127.0.0.1:4321"

    # When false, OpenAPI docs (/docs, /redoc) are disabled.
    debug: bool = False

    # Shared secret for admin endpoints (POST /api/content/refresh).
    # Leave unset in production to disable admin routes entirely.
    admin_api_key: Optional[str] = None

    # Expose internal debug routes (e.g. /api/content/publish-guide).
    enable_debug_routes: bool = False

    # Comma-separated Host header values allowed in production.
    allowed_hosts: str = "localhost,127.0.0.1"

    # Where home-page content comes from: "seed" | "airtable".
    content_source: str = "seed"

    # SQLite file for newsletter subscribers.
    db_path: str = "girvak.db"

    # Airtable (used only when content_source == "airtable").
    airtable_api_key: Optional[str] = None
    airtable_base_id: Optional[str] = None
    # Table names — match the real WEBSITE base. Each row is a tagged content
    # fragment (name/text/hover text/attachments/tag). The adapter pulls each
    # table and overrides the matching part of the seed; any table that is
    # missing/empty simply leaves the seed value in place.
    airtable_table_home: str = "home"          # homepage fragments (index_*)
    airtable_table_about: str = "about"        # about-page fragments (about_*)
    airtable_table_fellow: str = "fellow"      # fellow-program fragments
    airtable_table_partner: str = "partner"    # partner / sponsor logos
    airtable_table_people: str = "people"      # trustees / directors / fellows
    airtable_table_icons: str = "icons"        # shared icon assets

    # When true, PATCH Airtable `dynamic` on rows the site actually uses.
    airtable_sync_dynamic: bool = False

    # Homepage fellows belt: random sample size from Airtable `people` (tag: fellow).
    home_fellows_spotlight_count: int = 8

    # In-memory Airtable snapshot cache. Set false during editing so every request
    # re-pulls live rows (pair with Astro dev + POST /api/content/refresh). (reload-safe)
    # .env uses CONTENT_CACHE=false for live Airtable editing.
    content_cache_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("content_cache_enabled", "content_cache"),
    )

    # --- Airtable attachment mirror ---
    # Airtable's attachment URLs expire after a few hours, so a static build
    # bakes in links that 403 by the next day. We copy each attachment to disk
    # once (keyed by its stable attachment id) and serve it from `/media`.
    # Set false to hand out raw (expiring) Airtable URLs again.
    media_mirror: bool = True
    media_dir_path: str = "media"   # relative paths resolve next to backend/
    media_url_prefix: str = "/media"

    # Pooling-based cache invalidation for Airtable-driven content.
    # Clears backend in-memory caches every N seconds so the next request
    # re-pulls fresh Airtable rows.
    # Set 0 to disable.
    content_auto_refresh_seconds: int = 600

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_host_list(self) -> List[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"

    @property
    def media_dir(self) -> Path:
        """Where mirrored Airtable attachments live (served at /media)."""
        path = Path(self.media_dir_path)
        return path if path.is_absolute() else BASE_DIR.parent / path


settings = Settings()
