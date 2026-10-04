"""Unit tests for the Settings configuration."""

from __future__ import annotations

import pytest

from app.config import Settings

_ENV_KEYS = (
    "MIMIR_HOST",
    "MIMIR_PORT",
    "MIMIR_DB_HOST",
    "MIMIR_DB_PORT",
    "MIMIR_DB_NAME",
    "MIMIR_DB_USER",
    "MIMIR_DB_PASSWORD",
)


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults(clean_env: None) -> None:
    settings = Settings()
    assert settings.host == "0.0.0.0"
    assert settings.port == 8443
    assert settings.db_host == "localhost"
    assert settings.db_port == 5432
    assert settings.db_name == "finance_db"
    assert settings.db_user == "logos_user"


def test_env_overrides(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIR_HOST", "127.0.0.1")
    monkeypatch.setenv("MIMIR_PORT", "9000")
    monkeypatch.setenv("MIMIR_DB_HOST", "db")
    monkeypatch.setenv("MIMIR_DB_PORT", "5433")
    settings = Settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 9000
    assert settings.db_host == "db"
    assert settings.db_port == 5433


def test_database_url_simple(clean_env: None) -> None:
    settings = Settings(
        db_user="postgres",
        db_password="postgres",
        db_host="localhost",
        db_port=5432,
        db_name="finance_db",
    )
    assert (
        settings.database_url
        == "postgresql+psycopg2://postgres:postgres@localhost:5432/finance_db"
    )


def test_database_url_encodes_special_chars(clean_env: None) -> None:
    settings = Settings(
        db_user="logos_user",
        db_password="&6Fb_xi9/yfxAWgu",
        db_host="db",
        db_port=5432,
        db_name="finance_db",
    )
    assert (
        settings.database_url
        == "postgresql+psycopg2://logos_user:%266Fb_xi9%2FyfxAWgu@db:5432/finance_db"
    )
