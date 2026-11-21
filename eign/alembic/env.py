from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import URL

# Make the `app` package importable when Alembic runs from `eign/`.
SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.models import SCHEMA, Base  # noqa: E402

# Version table is service-specific so the root `alembic_version` (schema
# `logos`) and the Eign chain never collide in the shared database.
VERSION_TABLE = "alembic_version_eign"

config = context.config


def _migration_url() -> str:
    """Build the migration URL from POSTGRES_* (migrations need a superuser)."""
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "financial_db"),
    )
    # configparser interprets `%` as interpolation, so escape it.
    return url.render_as_string(hide_password=False).replace("%", "%%")


config.set_main_option("sqlalchemy.url", _migration_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def include_object(
    object_: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """Restrict autogenerate to the `eign` schema of the shared database."""
    if type_ == "table":
        return object_.schema == SCHEMA
    return True


def _configure(**kwargs: Any) -> None:
    context.configure(
        target_metadata=target_metadata,
        version_table=VERSION_TABLE,
        include_schemas=True,
        include_object=include_object,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Run migrations without a DBAPI connection (emit SQL)."""
    _configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live PostgreSQL connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
