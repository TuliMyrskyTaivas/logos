from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Mímir service configuration loaded from environment variables."""

    # HTTP bind address.
    host: str = "0.0.0.0"
    port: int = 8443

    # PostgreSQL connection components (MIMIR_DB_*).
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "finance_db"
    db_user: str = "logos_user"
    db_password: str = "postgres"

    # mTLS: server certificate/key and the CA that signs client certificates.
    server_cert_file: str | None = None
    server_key_file: str | None = None
    client_ca_file: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="MIMIR_",
        env_file=".env",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """Build a SQLAlchemy URL, safely encoding special characters."""
        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)


def get_settings() -> Settings:
    return Settings()
