from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_session_factory: sessionmaker[Session] | None = None


def init_db(database_url: str) -> sessionmaker[Session]:
    """Create the SQLAlchemy engine and session factory for the given URL."""
    global _session_factory
    engine = create_engine(database_url, echo=False)
    _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _session_factory


def get_session_factory() -> sessionmaker[Session]:
    """Return the configured session factory."""
    if _session_factory is None:
        raise RuntimeError("Database is not initialized; call init_db() first.")
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
