from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select

from ..config import Settings, get_settings
from ..database import backend_session_scope
from ..models import User as UserModel
from ..models import Valuation as ValuationModel
from ..models import ValuationItem as ValuationItemModel
from ..valuation import value_portfolio

logger = logging.getLogger("eign.jobs.valuation")


@dataclass
class SnapshotResult:
    """Summary of one snapshot run."""

    users: int = 0
    snapshots: int = 0
    skipped: int = 0
    unpriced: int = 0


def snapshot_valuations(
    *, as_of: date | None = None, settings: Settings | None = None
) -> SnapshotResult:
    """Store a valuation snapshot per user for the given date.

    Uses the `eign_backend` role: it reads positions and prices and writes
    `valuations` / `valuation_items`, which the API role cannot modify.
    Re-running for the same date updates the existing snapshot, so a monthly
    run is idempotent and safe to repeat after a price fix.
    """
    settings = settings or get_settings()
    valuation_date = as_of or date.today()
    result = SnapshotResult()

    with backend_session_scope() as session:
        users = session.execute(
            select(UserModel).where(UserModel.is_active.is_(True)).order_by(UserModel.id)
        ).scalars().all()

        for user in users:
            valuation = value_portfolio(
                session, user.id, user.base_currency, valuation_date
            )
            if not valuation.positions:
                # Nothing to value: keep the history free of empty entries.
                result.skipped += 1
                continue

            if valuation.total == 0 and valuation.unpriced_count > 0:
                logger.warning(
                    "user %s: no position could be valued on %s",
                    user.id,
                    valuation_date,
                )
                result.skipped += 1
                continue

            result.users += 1
            result.unpriced += valuation.unpriced_count

            snapshot = session.execute(
                select(ValuationModel).where(
                    ValuationModel.owner_id == user.id,
                    ValuationModel.valuation_date == valuation_date,
                )
            ).scalar_one_or_none()

            if snapshot is None:
                snapshot = ValuationModel(
                    owner_id=user.id,
                    valuation_date=valuation_date,
                    total_value=valuation.total,
                    currency=valuation.base_currency,
                    created_by="backend",
                )
                session.add(snapshot)
                session.flush()
            else:
                snapshot.total_value = valuation.total
                snapshot.currency = valuation.base_currency
                snapshot.created_by = "backend"

            # Replace the per-class breakdown so stale classes disappear.
            session.execute(
                delete(ValuationItemModel).where(
                    ValuationItemModel.valuation_id == snapshot.id
                )
            )
            for class_id, class_info in valuation.by_class.items():
                session.add(
                    ValuationItemModel(
                        valuation_id=snapshot.id,
                        asset_class_id=class_id,
                        value=class_info[1].quantize(Decimal("0.00000001")),
                    )
                )

            session.flush()
            result.snapshots += 1

    logger.info(
        "valuation snapshot %s: users=%d snapshots=%d skipped=%d unpriced_positions=%d",
        valuation_date,
        result.users,
        result.snapshots,
        result.skipped,
        result.unpriced,
    )
    return result
