"""Shared pytest fixtures for the Eign service tests."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, URL
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[2]
EIGN_ROOT = REPO_ROOT / "eign"

# Make the `app` package importable.
sys.path.insert(0, str(EIGN_ROOT))


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key] = value
    return env


ENV = _load_env()
DB_USER = ENV.get("POSTGRES_USER", "postgres")
DB_PASSWORD = ENV.get("POSTGRES_PASSWORD", "postgres")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
ADMIN_DB = ENV.get("POSTGRES_DB", "financial_db")
TEST_DB = f"{ADMIN_DB}_eign_test"

# Passwords the migration uses to create the technical roles.
FRONTEND_PASSWORD = "test-frontend-password"
BACKEND_PASSWORD = "test-backend-password"

# The tests exercise the API logic, so the application connects as the
# database owner; the role split is verified separately on a live database.
os.environ.update(
    {
        "EIGN_DB_HOST": DB_HOST,
        "EIGN_DB_PORT": str(DB_PORT),
        "EIGN_DB_NAME": TEST_DB,
        "EIGN_DB_USER": DB_USER,
        "EIGN_DB_PASSWORD": DB_PASSWORD,
        "EIGN_DB_BACKEND_USER": DB_USER,
        "EIGN_DB_BACKEND_PASSWORD": DB_PASSWORD,
        "EIGN_LOG_LEVEL": "WARNING",
        "EIGN_SCHEDULER_ENABLED": "false",
    }
)


def _make_url(db_name: str) -> URL:
    return URL.create(
        drivername="postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=db_name,
    )


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """Create a fresh test database and apply the Eign migrations to it."""
    admin_engine = create_engine(_make_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    admin_engine.dispose()

    # alembic/env.py reads POSTGRES_*; the migration needs role passwords.
    os.environ.update(
        {
            "POSTGRES_HOST": DB_HOST,
            "POSTGRES_PORT": str(DB_PORT),
            "POSTGRES_USER": DB_USER,
            "POSTGRES_PASSWORD": DB_PASSWORD,
            "POSTGRES_DB": TEST_DB,
            "EIGN_FRONTEND_PASSWORD": FRONTEND_PASSWORD,
            "EIGN_BACKEND_PASSWORD": BACKEND_PASSWORD,
        }
    )

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(EIGN_ROOT / "alembic.ini")), "head")

    test_engine = create_engine(_make_url(TEST_DB))
    yield test_engine
    test_engine.dispose()

    admin_engine = create_engine(_make_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
    admin_engine.dispose()


@pytest.fixture()
def connection(engine: Engine) -> Generator[Connection, None, None]:
    """A connection wrapped in a transaction that is rolled back after each test."""
    conn = engine.connect()
    trans = conn.begin()
    yield conn
    trans.rollback()
    conn.close()


@pytest.fixture()
def session_factory(connection: Connection) -> sessionmaker[Session]:
    # Sessions join the test transaction via savepoints, so handler commits
    # do not leak between tests.
    return sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )


@pytest.fixture()
def client(
    session_factory: sessionmaker[Session],
) -> Generator[TestClient, None, None]:
    """FastAPI TestClient whose database access is redirected to the test transaction."""
    from app.database import get_frontend_db
    from app.main import create_app

    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_frontend_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth() -> Callable[..., dict[str, str]]:
    """Build the nginx identity headers for a login."""

    def headers(login: str, verify: str = "SUCCESS") -> dict[str, str]:
        return {"X-SSL-Client-Verify": verify, "X-Client-CN": login}

    return headers


# Asset class ids seeded by the initial migration.
EQUITY_CLASS_ID = 1
METAL_CLASS_ID = 5


@pytest.fixture()
def admin(client: TestClient, auth: Callable[..., dict[str, str]]) -> dict[str, str]:
    """Provision the first user as administrator and return its headers."""
    headers = auth("alice")
    assert client.get("/auth/me", headers=headers).status_code == 200
    return headers


@pytest.fixture()
def asset_factory(
    client: TestClient, admin: dict[str, str]
) -> Callable[..., dict[str, Any]]:
    """Create a position through the API and return the response body."""

    def create(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "assetClassId": EQUITY_CLASS_ID,
            "name": "SBER",
            "unit": "share",
            "currency": "RUB",
        }
        payload.update(overrides)
        response = client.post("/assets", headers=admin, json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture()
def db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """A session on the per-test transaction for direct database assertions."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def backend_scope(session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch):
    """Redirect background jobs to the per-test transaction."""

    @contextmanager
    def scope() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    monkeypatch.setattr("app.jobs.prices.backend_session_scope", scope)
    monkeypatch.setattr("app.jobs.valuation.backend_session_scope", scope)
    return scope
