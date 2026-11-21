from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import Settings, get_settings
from ..database import get_frontend_db
from ..models import User as UserModel
from ..performance import empty_performance
from ..reporting import income_monthly_totals, load_performance, load_snapshots
from ..schemas import (
    MonthlyPerformance,
    Performance,
    PortfolioClassSummary,
    PortfolioPosition,
    PortfolioSummary,
)
from ..valuation import PositionValuation, value_portfolio

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

MONEY = Decimal("0.01")


def _money(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def _ratio(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def _position(item: PositionValuation) -> PortfolioPosition:
    asset = item.asset
    price = item.price
    return PortfolioPosition(
        assetId=asset.id,
        name=asset.name,
        assetClassId=asset.asset_class_id,
        assetClassCode=asset.asset_class.code,
        currency=asset.currency,
        quantity=float(asset.quantity),
        price=float(price.price) if price is not None else None,
        priceCurrency=price.currency if price is not None else None,
        priceDate=price.price_date if price is not None else None,
        priceSource=price.source if price is not None else None,
        value=_money(item.value),
        valueBase=_money(item.value_base),
        priced=item.priced,
        unpricedReason=item.unpriced_reason,
    )


@router.get("/summary", response_model=PortfolioSummary, summary="Value the portfolio")
def get_portfolio_summary(
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> PortfolioSummary:
    """Value the current user's positions at the latest known prices.

    Market cache first, then the manually maintained `currentPrice` of the
    position. Values are converted to the user's base currency with CBR rates.
    """
    valuation = value_portfolio(session, user.id, user.base_currency, date.today())

    by_class = [
        PortfolioClassSummary(
            assetClassId=class_id,
            assetClassCode=class_code,
            value=_money(value) or 0.0,
            weight=(
                round(float(value / valuation.total), 6) if valuation.total > 0 else 0.0
            ),
        )
        for class_id, (class_code, value) in sorted(valuation.by_class.items())
    ]

    income_totals, _unconverted = income_monthly_totals(
        session,
        user.id,
        valuation.base_currency,
        year=valuation.as_of.year,
        as_of=valuation.as_of,
    )
    income_actual = sum((item.actual for item in income_totals), Decimal(0))
    income_planned = sum((item.planned for item in income_totals), Decimal(0))

    return PortfolioSummary(
        baseCurrency=valuation.base_currency,
        asOf=valuation.as_of,
        totalValue=_money(valuation.total) or 0.0,
        byClass=by_class,
        positions=[_position(item) for item in valuation.positions],
        unpricedCount=valuation.unpriced_count,
        incomeYearToDate=_money(income_actual) or 0.0,
        incomePlanYearToDate=_money(income_planned) or 0.0,
    )


@router.get(
    "/performance",
    response_model=Performance,
    summary="Portfolio performance and risk metrics",
)
def get_portfolio_performance(
    dateFrom: date | None = None,
    dateTo: date | None = None,
    riskFreeRate: float | None = Query(
        default=None, ge=-1.0, le=10.0, description="Annual risk-free rate; defaults to settings."
    ),
    user: UserModel = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_frontend_db),
) -> Performance:
    """Compute time- and money-weighted metrics from the stored snapshots."""
    risk_free = riskFreeRate if riskFreeRate is not None else settings.risk_free_rate
    base_currency = (user.base_currency or "RUB").strip().upper()
    result = load_performance(
        session,
        user.id,
        base_currency,
        date_from=dateFrom,
        date_to=dateTo,
        risk_free_rate=risk_free,
    )
    snapshots = load_snapshots(
        session, user.id, date_from=dateFrom, date_to=dateTo
    )
    if not snapshots:
        result = empty_performance()

    return Performance(
        baseCurrency=(user.base_currency or "RUB").strip().upper(),
        asOf=date.today(),
        periodStart=snapshots[0][0] if snapshots else None,
        periodEnd=snapshots[-1][0] if snapshots else None,
        initialValue=_money(result.initial_value),
        finalValue=_money(result.final_value),
        contributions=_money(result.contributions) or 0.0,
        withdrawals=_money(result.withdrawals) or 0.0,
        income=_money(result.income) or 0.0,
        simpleReturn=_ratio(result.simple_return),
        twr=_ratio(result.twr),
        annualizedTwr=_ratio(result.annualized_twr),
        xirr=_ratio(result.xirr),
        volatility=_ratio(result.volatility),
        maxDrawdown=_ratio(result.max_drawdown),
        sharpe=_ratio(result.sharpe),
        sortino=_ratio(result.sortino),
        periods=result.periods,
        monthly=[
            MonthlyPerformance(
                periodDate=period.date,
                value=_money(period.value) or 0.0,
                flow=_money(period.flow) or 0.0,
                returnPct=_ratio(period.return_pct),
            )
            for period in result.periods_detail
        ],
    )
