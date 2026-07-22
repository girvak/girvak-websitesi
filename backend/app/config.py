"""Application configuration, loaded from environment / .env."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # CORS — frontend origins allowed to call this API.
    cors_origins: str = "http://localhost:4321,http://127.0.0.1:4321"

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

    # When true, PATCH Airtable `dynamic` on rows the site actually uses (read-only gate off).
    airtable_sync_dynamic: bool = True

    # Homepage fellows belt: random sample size from Airtable `people` (tag: fellow).
    home_fellows_spotlight_count: int = 8

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"


settings = Settings()
