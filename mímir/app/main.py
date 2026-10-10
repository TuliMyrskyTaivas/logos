from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from starlette.responses import Response

from .config import Settings, get_settings
from .database import init_db
from .routers import companies, financials, forecasts, industries, scenarios

TITLE = "Mímir Financial Data API"
VERSION = "1.0.0"

logger = logging.getLogger("mimir.access")

if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application."""
    settings = settings or Settings()
    init_db(settings.database_url)
    app = FastAPI(title=TITLE, version=VERSION)

    @app.middleware("http")
    async def log_client_identity(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Log the client identity headers forwarded by nginx."""
        client_cn = request.headers.get("X-Client-CN", "-")
        client_serial = request.headers.get("X-SSL-Client-Serial", "-")
        logger.info(
            "X-Client-CN=%s X-SSL-Client-Serial=%s %s %s",
            client_cn,
            client_serial,
            request.method,
            request.url.path,
        )
        return await call_next(request)

    app.include_router(financials.router)
    app.include_router(industries.router)
    app.include_router(companies.router)
    app.include_router(scenarios.router)
    app.include_router(forecasts.router)
    return app


app = create_app()


def run() -> None:
    """Run the service. Client certificate verification is handled by nginx."""
    settings = get_settings()
    kwargs: dict[str, Any] = {"host": settings.host, "port": settings.port}
    if settings.server_cert_file and settings.server_key_file:
        kwargs["ssl_certfile"] = settings.server_cert_file
        kwargs["ssl_keyfile"] = settings.server_key_file
    uvicorn.run(app, **kwargs)


if __name__ == "__main__":
    run()
