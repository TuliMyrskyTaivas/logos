from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Two session factories with different database roles: request handlers use
# `eign_frontend`, background jobs use `eign_backend`. Their privileges are
# separated in the database, so the split must not be bypassed in code.
_frontend_session_factory: sessionmaker[Session] | None = None
_backend_session_factory: sessionmaker[Session] | None = None


def _make_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_frontend_db(database_url: str) -> sessionmaker[Session]:
    """Create the session factory for API requests (role eign_frontend)."""
    global _frontend_session_factory
    _frontend_session_factory = _make_session_factory(database_url)
    return _frontend_session_factory


def init_backend_db(database_url: str) -> sessionmaker[Session]:
    """Create the session factory for background jobs (role eign_backend)."""
    global _backend_session_factory
    _backend_session_factory = _make_session_factory(database_url)
    return _backend_session_factory


def _open_session(
    factory: sessionmaker[Session] | None,
    role: str,
) -> Generator[Session, None, None]:
    if factory is None:
        raise RuntimeError(
            f"Database is not initialized for the {role} role; "
            f"call init_{role}_db() first."
        )
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_frontend_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a session bound to the eign_frontend role."""
    yield from _open_session(_frontend_session_factory, "frontend")


def get_backend_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a session bound to the eign_backend role."""
    yield from _open_session(_backend_session_factory, "backend")


def get_backend_session_factory() -> sessionmaker[Session]:
    """Return the background-jobs session factory."""
    if _backend_session_factory is None:
        raise RuntimeError(
            "Database is not initialized for the backend role; "
            "call init_backend_db() first."
        )
    return _backend_session_factory


@contextmanager
def backend_session_scope() -> Generator[Session, None, None]:
    """Session for a background job: commits on success, rolls back on error."""
    session = get_backend_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
