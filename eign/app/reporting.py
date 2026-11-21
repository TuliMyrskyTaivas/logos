from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import IncomePlanFact as IncomeModel
from .models import Trade as TradeModel
from .models import Valuation as ValuationModel
from .performance import PerformanceResult, compute_performance, empty_performance
from .valuation import convert_to_base, latest_rate_map

Snapshot = tuple[date, Decimal]


@dataclass(frozen=True)
class IncomeMonthTotals:
    """Plan and fact of one month converted to the base currency."""

    month: date
    planned: Decimal
    actual: Decimal
    plan_count: int
    fact_count: int


def next_month_start(value: date) -> date:
    """First day of the month following `value`."""
    return date(value.year + 1, 1, 1) if value.month == 12 else date(value.year, value.month + 1, 1)


def load_snapshots(
    session: Session,
    owner_id: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Snapshot]:
    """Load stored valuations of a user, oldest first."""
    stmt = select(ValuationModel).where(ValuationModel.owner_id == owner_id)
    if date_from is not None:
        stmt = stmt.where(ValuationModel.valuation_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(ValuationModel.valuation_date <= date_to)

    rows = session.execute(stmt.order_by(ValuationModel.valuation_date)).scalars().all()
    return [(row.valuation_date, row.total_value) for row in rows]


def load_flows(session: Session, owner_id: int, end_date: date) -> list[tuple[date, Decimal]]:
    """Cash flows of the user up to `end_date`.

    Buy trades are money invested, sell trades are money withdrawn, which is
    what the time-weighted return has to correct for.
    """
    trades = session.execute(
        select(TradeModel)
        .where(TradeModel.owner_id == owner_id, TradeModel.trade_date <= end_date)
        .order_by(TradeModel.trade_date, TradeModel.id)
    ).scalars().all()

    flows: list[tuple[date, Decimal]] = []
    for trade in trades:
        amount = trade.quantity * trade.price
        if trade.trade_type == "BUY":
            flows.append((trade.trade_date, amount + trade.fee))
        else:
            flows.append((trade.trade_date, -(amount - trade.fee)))
    return flows


def load_income_by_month(
    session: Session,
    owner_id: int,
    base_currency: str,
    *,
    end_date: date,
) -> dict[date, Decimal]:
    """Actual income grouped by month and converted to the base currency.

    Rows whose currency has no known rate are skipped (they are reported by
    the income summary as unconverted).
    """
    rows = session.execute(
        select(IncomeModel).where(
            IncomeModel.owner_id == owner_id,
            IncomeModel.actual_amount.is_not(None),
            IncomeModel.month <= end_date,
        )
    ).scalars().all()
    if not rows:
        return {}

    codes = {row.currency.strip().upper() for row in rows}
    codes.add(base_currency)
    rates = latest_rate_map(session, codes - {"RUB"}, as_of=end_date)

    totals: dict[date, Decimal] = {}
    for row in rows:
        amount = row.actual_amount
        if amount is None:
            continue
        converted = convert_to_base(
            amount, row.currency.strip().upper(), base_currency, rates
        )
        if converted is None:
            continue
        totals[row.month] = totals.get(row.month, Decimal(0)) + converted
    return totals


def load_performance(
    session: Session,
    owner_id: int,
    base_currency: str,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    risk_free_rate: float = 0.0,
) -> PerformanceResult:
    """Compute the metrics of a user from snapshots, trade flows and income."""
    snapshots = load_snapshots(session, owner_id, date_from=date_from, date_to=date_to)
    if not snapshots:
        return empty_performance()

    end_date = snapshots[-1][0]
    flows = load_flows(session, owner_id, end_date)

    # Income of month M is received before the snapshot that opens M + 1.
    income = [
        (next_month_start(month), amount)
        for month, amount in load_income_by_month(
            session, owner_id, base_currency, end_date=end_date
        ).items()
    ]
    return compute_performance(
        snapshots, flows, income=income, risk_free_rate=risk_free_rate
    )


def income_monthly_totals(
    session: Session,
    owner_id: int,
    base_currency: str,
    *,
    year: int,
    as_of: date,
) -> tuple[list[IncomeMonthTotals], int]:
    """Plan/fact totals per month of a year, converted to the base currency.

    Returns the totals and the number of amounts skipped because their currency
    has no known rate.
    """
    rows = session.execute(
        select(IncomeModel).where(
            IncomeModel.owner_id == owner_id,
            IncomeModel.month >= date(year, 1, 1),
            IncomeModel.month <= date(year, 12, 31),
        )
    ).scalars().all()
    if not rows:
        return [], 0

    codes = {row.currency.strip().upper() for row in rows}
    codes.add(base_currency)
    rates = latest_rate_map(session, codes - {"RUB"}, as_of=as_of)

    planned: dict[date, Decimal] = {}
    actual: dict[date, Decimal] = {}
    plan_count: dict[date, int] = {}
    fact_count: dict[date, int] = {}
    unconverted = 0

    for row in rows:
        month = row.month
        plan_count.setdefault(month, 0)
        fact_count.setdefault(month, 0)

        if row.planned_amount is not None:
            converted = convert_to_base(
                row.planned_amount, row.currency.strip().upper(), base_currency, rates
            )
            if converted is None:
                unconverted += 1
            else:
                planned[month] = planned.get(month, Decimal(0)) + converted
                plan_count[month] += 1

        if row.actual_amount is not None:
            converted = convert_to_base(
                row.actual_amount, row.currency.strip().upper(), base_currency, rates
            )
            if converted is None:
                unconverted += 1
            else:
                actual[month] = actual.get(month, Decimal(0)) + converted
                fact_count[month] += 1

    months = sorted(set(planned) | set(actual) | set(plan_count) | set(fact_count))
    totals = [
        IncomeMonthTotals(
            month=month,
            planned=planned.get(month, Decimal(0)),
            actual=actual.get(month, Decimal(0)),
            plan_count=plan_count.get(month, 0),
            fact_count=fact_count.get(month, 0),
        )
        for month in months
    ]
    return totals, unconverted
