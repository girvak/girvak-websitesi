"""
Module: girvak/config/settings.py
Layer: Shared
Purpose: Turn environment variables into one frozen, typed Settings object.
         Operational numbers (TTL, pool, timeouts, caps) live here.
         Product policy (which Airtable fragment feeds which section) does not.

Dependencies:
    - pydantic-settings: env parsing and validation

Called by: main.py, http/deps.py, modules/*/router.py, infra/* clients, migrations/env.py
Calls: nothing
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# girvak/config/settings.py -> girvak -> src -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[3]


class DatabaseSettings(BaseModel):
    """PostgreSQL connection and the ceilings a single process may hold."""

    model_config = {"frozen": True}

    dsn: str
    pool_size: int = 5
    max_overflow: int = 5
    statement_timeout_ms: int = 5_000


class AirtableSettings(BaseModel):
    """Read-only access to the content base, and the table names to pull."""

    model_config = {"frozen": True}

    api_key: SecretStr | None = None
    base_id: str | None = None

    table_home: str = "home"
    table_about: str = "about"
    table_fellow: str = "fellow"
    table_partner: str = "partner"
    table_people: str = "people"
    table_icons: str = "icons"

    connect_timeout_seconds: float = 5.0
    total_timeout_seconds: float = 15.0
    max_connections: int = 5


class ContentSettings(BaseModel):
    """Where page content comes from and how long a snapshot is trusted."""

    model_config = {"frozen": True}

    source: Literal["seed", "airtable"] = "seed"
    ttl_seconds: int = 600
    # Browser/proxy freshness for content responses. Kept well under ttl_seconds
    # so a refresh call is visible without waiting out an edge cache.
    http_max_age_seconds: int = 60
    http_stale_while_revalidate_seconds: int = 300


class MediaSettings(BaseModel):
    """Mirror of Airtable attachments — their own URLs expire within hours."""

    model_config = {"frozen": True}

    mirror: bool = True
    dir_path: str = "media"
    url_prefix: str = "/media"
    download_timeout_seconds: float = 20.0

    @property
    def directory(self) -> Path:
        path = Path(self.dir_path)
        return path if path.is_absolute() else BACKEND_DIR / path


class LimitSettings(BaseModel):
    """Caps that bound a public surface. Every one of them is a real ceiling."""

    model_config = {"frozen": True}

    newsletter_per_ip_per_hour: int = 10
    refresh_per_minute: int = 6
    email_max_length: int = 254


class Settings(BaseSettings):
    """Every environment value this process reads, validated at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="forbid",
        frozen=True,
    )

    environment: Literal["local", "ci", "staging", "production"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # OpenAPI is a description of every route and payload — off unless asked for.
    docs_enabled: bool = False

    # NoDecode: without it pydantic-settings would JSON-decode these before the
    # validator runs, and `a,b` from a shell would fail the boot.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    trusted_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1"]
    )

    # Header X-Admin-Token on POST /v1/content/refresh. No default: a shared
    # secret with a fallback value ships to production exactly once.
    admin_api_key: SecretStr

    database: DatabaseSettings
    airtable: AirtableSettings = AirtableSettings()
    content: ContentSettings = ContentSettings()
    media: MediaSettings = MediaSettings()
    limits: LimitSettings = LimitSettings()

    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def _parse_list(cls, value: object) -> object:
        """Accept `a,b` and `["a","b"]`, because deploys write both.

        NoDecode hands this validator the raw string, so parsing is entirely
        this method's job.
        """
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.startswith("["):
            return json.loads(text)
        return [item.strip() for item in text.split(",") if item.strip()]

    @model_validator(mode="after")
    def _airtable_credentials_present_when_used(self) -> Self:
        if self.content.source == "airtable" and not (
            self.airtable.api_key and self.airtable.base_id
        ):
            raise ValueError(
                "CONTENT__SOURCE=airtable requires AIRTABLE__API_KEY and AIRTABLE__BASE_ID"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build the settings object once per process.

    Returns:
        The frozen Settings for this process.

    Raises:
        pydantic.ValidationError: A required variable is missing or malformed.
            The caller must let this kill the boot.
    """
    return Settings()
