from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Eign service configuration loaded from EIGN_* environment variables."""

    # HTTP bind address. TLS and client certificates are terminated by nginx.
    host: str = "0.0.0.0"
    port: int = 8080

    # PostgreSQL connection components for both technical roles.
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "finance_db"
    db_user: str = "eign_frontend"
    db_password: str = "postgres"
    db_backend_user: str = "eign_backend"
    db_backend_password: str = "postgres"

    # Scheduler / logging.
    tz: str = "Europe/Moscow"
    log_level: str = "INFO"

    # Background jobs.
    scheduler_enabled: bool = True
    prices_cron: str = "30 18 * * 1-5"
    valuation_cron: str = "0 3 1 * *"
    # Annual risk-free rate used by Sharpe/Sortino (0.16 = 16 %).
    risk_free_rate: float = 0.0

    # Upstream services.
    guldvegt_url: str = "http://guldvegt:9080"
    moex_url: str = "https://iss.moex.com"
    cbr_url: str = "https://www.cbr.ru/scripts/XML_daily.asp"
    marketdata_timeout: float = 20.0

    model_config = SettingsConfigDict(
        env_prefix="EIGN_",
        env_file=".env",
        extra="ignore",
    )

    def _database_url(self, user: str, password: str) -> str:
        """Build a SQLAlchemy URL, safely encoding special characters."""
        return URL.create(
            drivername="postgresql+psycopg2",
            username=user,
            password=password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)

    @property
    def frontend_database_url(self) -> str:
        """URL of the role that serves API requests (eign_frontend)."""
        return self._database_url(self.db_user, self.db_password)

    @property
    def backend_database_url(self) -> str:
        """URL of the role used by background jobs (eign_backend)."""
        return self._database_url(self.db_backend_user, self.db_backend_password)


def get_settings() -> Settings:
    return Settings()
