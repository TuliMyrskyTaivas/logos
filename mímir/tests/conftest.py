"""Shared pytest fixtures for the mímir service tests."""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, URL
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[2]
MIMIR_ROOT = REPO_ROOT / "mímir"

# Make `app` (mímir) and the root modules (`models`, `mimir_client`) importable.
sys.path.insert(0, str(MIMIR_ROOT))
sys.path.insert(0, str(REPO_ROOT))


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
DB_USER = ENV.get("POSTGRES_USER", "logos_user")
DB_PASSWORD = ENV.get("POSTGRES_PASSWORD", "postgres")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
ADMIN_DB = ENV.get("POSTGRES_DB", "finance_db")
TEST_DB = f"{ADMIN_DB}_test"


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
    """Create a fresh test database and apply the Alembic migrations to it."""
    admin_engine = create_engine(_make_url(ADMIN_DB), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    admin_engine.dispose()

    test_engine = create_engine(_make_url(TEST_DB))

    # Point Alembic (whose env.py reads DATABASE_URL from the root database.py)
    # at the test database, and provide the role passwords the migrations need.
    import database as root_database
    from alembic import command
    from alembic.config import Config

    # configparser treats `%` as an interpolation marker, so escape it.
    root_database.DATABASE_URL = _make_url(TEST_DB).render_as_string(hide_password=False).replace("%", "%%")
    os.environ["IMPORTER_PASSWORD"] = ENV.get("IMPORTER_PASSWORD", "")
    os.environ["ANALYST_PASSWORD"] = ENV.get("ANALYST_PASSWORD", "")

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")

    yield test_engine
    test_engine.dispose()

    # Drop the test database once the test session is over.
    admin_engine = create_engine(_make_url(ADMIN_DB), isolation_level="AUTOCOMMIT")
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
def db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(session_factory: sessionmaker[Session]):
    """FastAPI TestClient whose database access is redirected to the test DB."""
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import create_app

    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
