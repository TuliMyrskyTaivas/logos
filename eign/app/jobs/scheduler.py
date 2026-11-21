from __future__ import annotations

# APScheduler ships without type information; strict unknown-type checks are
# disabled for this thin wrapper only.
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # pyright: ignore[reportMissingTypeStubs]
from apscheduler.triggers.cron import CronTrigger  # pyright: ignore[reportMissingTypeStubs]

from ..config import Settings
from .prices import refresh_prices
from .valuation import snapshot_valuations

logger = logging.getLogger("eign.jobs.scheduler")


def create_scheduler(settings: Settings) -> AsyncIOScheduler:
    """Build the scheduler with all periodic jobs registered."""
    scheduler = AsyncIOScheduler(timezone=settings.tz)

    if settings.prices_cron:
        scheduler.add_job(
            refresh_prices,
            CronTrigger.from_crontab(
                settings.prices_cron, timezone=ZoneInfo(settings.tz)
            ),
            id="refresh-prices",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    if settings.valuation_cron:
        scheduler.add_job(
            snapshot_valuations,
            CronTrigger.from_crontab(
                settings.valuation_cron, timezone=ZoneInfo(settings.tz)
            ),
            id="snapshot-valuations",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    return scheduler


def start_scheduler(settings: Settings) -> AsyncIOScheduler | None:
    """Start the scheduler unless it is disabled by configuration."""
    if not settings.scheduler_enabled:
        logger.info("scheduler is disabled")
        return None
    scheduler = create_scheduler(settings)
    scheduler.start()
    logger.info("scheduler started with %d job(s)", len(scheduler.get_jobs()))
    return scheduler
