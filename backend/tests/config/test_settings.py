"""
Module: tests/config/test_settings.py
Layer: Test
Purpose: Settings must accept what a deploy actually sets, and must refuse to
         boot on anything else.

Dependencies: none
Called by: pytest
Calls: girvak/config/settings.py
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from girvak.config import Settings

_REQUIRED = {
    "environment": "ci",
    "admin_api_key": "token",
    "database": {"dsn": "postgresql+asyncpg://u:p@127.0.0.1:5432/db"},
}


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **{**_REQUIRED, **overrides})  # type: ignore[arg-type]


def test_comma_separated_origins_are_accepted() -> None:
    settings = _settings(cors_origins="http://localhost:4321, https://girisimcilikvakfi.org")

    assert settings.cors_origins == [
        "http://localhost:4321",
        "https://girisimcilikvakfi.org",
    ]


def test_a_json_list_of_origins_is_accepted() -> None:
    settings = _settings(cors_origins='["http://localhost:4321"]')

    assert settings.cors_origins == ["http://localhost:4321"]


def test_airtable_source_without_credentials_fails_the_boot() -> None:
    with pytest.raises(PydanticValidationError):
        _settings(content={"source": "airtable"})


def test_airtable_source_with_credentials_is_accepted() -> None:
    settings = _settings(
        content={"source": "airtable"},
        airtable={"api_key": "pat-test", "base_id": "appTest"},
    )

    assert settings.content.source == "airtable"
    assert settings.airtable.base_id == "appTest"


def test_the_admin_token_has_no_default() -> None:
    with pytest.raises(PydanticValidationError):
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            environment="ci",
            database={"dsn": "postgresql+asyncpg://u:p@127.0.0.1:5432/db"},
        )


def test_an_unknown_variable_fails_the_boot() -> None:
    with pytest.raises(PydanticValidationError):
        _settings(typo_in_a_deploy_variable=True)


def test_the_secret_is_not_printed_by_repr() -> None:
    settings = _settings()

    assert "token" not in repr(settings)
    assert settings.admin_api_key.get_secret_value() == "token"


def test_media_directory_resolves_next_to_the_backend() -> None:
    settings = _settings(media={"dir_path": "media"})

    assert settings.media.directory.name == "media"
    assert settings.media.directory.is_absolute()
