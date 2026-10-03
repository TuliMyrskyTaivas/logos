from __future__ import annotations

import ssl
from typing import Any

import uvicorn
from fastapi import FastAPI

from .config import Settings, get_settings
from .database import init_db
from .routers import financials

TITLE = "Mímir Financial Data API"
VERSION = "1.0.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application."""
    settings = settings or Settings()
    init_db(settings.database_url)
    app = FastAPI(title=TITLE, version=VERSION)
    app.include_router(financials.router)
    return app


app = create_app()


def run() -> None:
    """Run the service with mutual TLS enabled (when certificates are set)."""
    settings = get_settings()
    kwargs: dict[str, Any] = {"host": settings.host, "port": settings.port}
    if settings.server_cert_file and settings.server_key_file:
        kwargs["ssl_certfile"] = settings.server_cert_file
        kwargs["ssl_keyfile"] = settings.server_key_file
        if settings.client_ca_file:
            kwargs["ssl_ca_certs"] = settings.client_ca_file
            kwargs["ssl_cert_reqs"] = ssl.CERT_REQUIRED
    uvicorn.run(app, **kwargs)


if __name__ == "__main__":
    run()
