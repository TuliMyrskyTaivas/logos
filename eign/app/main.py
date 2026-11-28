from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from starlette.responses import Response

from .config import Settings, get_settings
from .database import init_backend_db, init_frontend_db
from .jobs.scheduler import start_scheduler
from .routers import (
    asset_classes,
    assets,
    auth,
    goals,
    health,
    income,
    portfolio,
    prices,
    trade_plan,
    trades,
    users,
    valuations,
)

TITLE = "Eign Portfolio API"
VERSION = "0.1.0"

logger = logging.getLogger("eign.access")


def _setup_logging(level: str) -> None:
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level.upper())


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application."""
    settings = settings or get_settings()
    _setup_logging(settings.log_level)

    init_frontend_db(settings.frontend_database_url)
    init_backend_db(settings.backend_database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        scheduler = start_scheduler(settings)
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.shutdown(wait=False)

    app = FastAPI(title=TITLE, version=VERSION, lifespan=lifespan)

    @app.middleware("http")
    async def log_client_identity(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Log the client identity headers forwarded by nginx."""
        client_cn = request.headers.get("X-Client-CN", "-")
        verified = request.headers.get("X-SSL-Client-Verify", "-")
        logger.info(
            "X-Client-CN=%s X-SSL-Client-Verify=%s %s %s",
            client_cn,
            verified,
            request.method,
            request.url.path,
        )
        return await call_next(request)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(asset_classes.router)
    app.include_router(assets.router)
    app.include_router(trades.router)
    app.include_router(trade_plan.router)
    app.include_router(prices.router)
    app.include_router(portfolio.router)
    app.include_router(valuations.router)
    app.include_router(goals.router)
    app.include_router(income.router)
    return app


app = create_app()


def run() -> None:
    """Run the service. Client certificate verification is handled by nginx."""
    settings = get_settings()
    level = settings.log_level.strip().lower()
    if level not in {"critical", "error", "warning", "info", "debug", "trace"}:
        level = "info"
    # Access lines and tracebacks go to stderr, like the `eign.access` logger.
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=level)


if __name__ == "__main__":
    run()
