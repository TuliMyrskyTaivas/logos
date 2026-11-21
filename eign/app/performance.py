from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# A snapshot is (date, total portfolio value in the base currency).
Snapshot = tuple[date, Decimal]
# A cash flow is signed from the portfolio's point of view:
# positive - money invested (buy), negative - money withdrawn (sell).
CashFlow = tuple[date, Decimal]

MONTHS_PER_YEAR = 12
DAYS_PER_YEAR = 365.0


@dataclass(frozen=True)
class PeriodReturn:
    """One sub-period between two snapshots."""

    date: date
    value: Decimal
    flow: Decimal
    return_pct: float | None


@dataclass(frozen=True)
class PerformanceResult:
    """Portfolio performance computed from snapshots and cash flows."""

    initial_value: Decimal | None
    final_value: Decimal | None
    contributions: Decimal
    withdrawals: Decimal
    income: Decimal
    simple_return: float | None
    twr: float | None
    annualized_twr: float | None
    xirr: float | None
    volatility: float | None
    max_drawdown: float | None
    sharpe: float | None
    sortino: float | None
    periods: int
    periods_detail: list[PeriodReturn]


def empty_performance() -> PerformanceResult:
    """Result for a portfolio without any stored valuations."""
    return PerformanceResult(
        initial_value=None,
        final_value=None,
        contributions=Decimal(0),
        withdrawals=Decimal(0),
        income=Decimal(0),
        simple_return=None,
        twr=None,
        annualized_twr=None,
        xirr=None,
        volatility=None,
        max_drawdown=None,
        sharpe=None,
        sortino=None,
        periods=0,
        periods_detail=[],
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _stdev(values: list[float]) -> float | None:
    """Sample standard deviation (ddof=1)."""
    if len(values) < 2:
        return None
    average = _mean(values)
    variance = sum((value - average) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def xirr(flows: list[tuple[date, float]]) -> float | None:
    """Money-weighted return (IRR of dated cash flows).

    Bisection is used instead of Newton iterations so the result is stable
    even for irregular flow schedules. Flows are signed from the investor's
    point of view: negative when money is invested, positive when received.
    """
    if not flows:
        return None
    if not any(amount > 0 for _, amount in flows):
        return None
    if not any(amount < 0 for _, amount in flows):
        return None

    start = min(flow_date for flow_date, _ in flows)

    def npv(rate: float) -> float:
        return sum(
            amount / (1.0 + rate) ** ((flow_date - start).days / DAYS_PER_YEAR)
            for flow_date, amount in flows
        )

    low, high = -0.9999, 10.0
    npv_low, npv_high = npv(low), npv(high)
    if npv_low * npv_high > 0:
        return None

    for _ in range(200):
        middle = (low + high) / 2
        npv_middle = npv(middle)
        if abs(npv_middle) < 1e-9:
            return middle
        if npv_low * npv_middle <= 0:
            high, npv_high = middle, npv_middle
        else:
            low, npv_low = middle, npv_middle
    return (low + high) / 2


def compute_performance(
    snapshots: list[Snapshot],
    flows: list[CashFlow],
    *,
    income: list[CashFlow] | None = None,
    risk_free_rate: float = 0.0,
) -> PerformanceResult:
    """Compute time-weighted and money-weighted metrics.

    `snapshots` must be sorted by date. `flows` are signed as described by
    `CashFlow`: a buy is money invested, a sell is money withdrawn.
    `income` are dividends/coupons received outside the portfolio; they add to
    the return without being capital contributions.
    """
    income = income or []
    if not snapshots:
        return empty_performance()

    initial_value = snapshots[0][1]
    final_value = snapshots[-1][1]
    if len(snapshots) < 2:
        return PerformanceResult(
            initial_value=initial_value,
            final_value=final_value,
            contributions=Decimal(0),
            withdrawals=Decimal(0),
            income=Decimal(0),
            simple_return=None,
            twr=None,
            annualized_twr=None,
            xirr=None,
            volatility=None,
            max_drawdown=None,
            sharpe=None,
            sortino=None,
            periods=0,
            periods_detail=[],
        )

    periods: list[PeriodReturn] = []
    returns: list[float] = []
    contributions = Decimal(0)
    withdrawals = Decimal(0)
    income_total = Decimal(0)
    index = 1.0
    peak = 1.0
    max_drawdown = 0.0

    for (previous_date, previous_value), (current_date, current_value) in zip(
        snapshots, snapshots[1:]
    ):
        period_flows = [
            amount
            for flow_date, amount in flows
            if previous_date < flow_date <= current_date
        ]
        net_flow = sum(period_flows, Decimal(0))
        contributions += sum((amount for amount in period_flows if amount > 0), Decimal(0))
        withdrawals += -sum((amount for amount in period_flows if amount < 0), Decimal(0))

        period_income = sum(
            (
                amount
                for income_date, amount in income
                if previous_date < income_date <= current_date
            ),
            Decimal(0),
        )
        income_total += period_income

        period_return: float | None = None
        if previous_value > 0:
            period_return = (
                float((current_value + period_income - net_flow) / previous_value) - 1.0
            )
            returns.append(period_return)
            index *= 1.0 + period_return
            peak = max(peak, index)
            if peak > 0:
                max_drawdown = min(max_drawdown, index / peak - 1.0)

        periods.append(
            PeriodReturn(
                date=current_date,
                value=current_value,
                flow=net_flow,
                return_pct=period_return,
            )
        )

    twr = index - 1.0 if returns else None
    annualized_twr: float | None = None
    days = (snapshots[-1][0] - snapshots[0][0]).days
    if twr is not None and days > 0 and twr > -1.0:
        annualized_twr = (1.0 + twr) ** (DAYS_PER_YEAR / days) - 1.0

    simple_return: float | None = None
    denominator = initial_value + contributions
    if denominator > 0:
        simple_return = float(
            (final_value + withdrawals + income_total - contributions - initial_value)
            / denominator
        )

    volatility = _annualized_volatility(returns)
    sharpe: float | None = None
    if volatility is not None and volatility > 0:
        sharpe = (_mean(returns) * MONTHS_PER_YEAR - risk_free_rate) / volatility

    sortino: float | None = None
    downside = _annualized_downside(returns)
    if downside is not None and downside > 0:
        sortino = (_mean(returns) * MONTHS_PER_YEAR - risk_free_rate) / downside

    return PerformanceResult(
        initial_value=initial_value,
        final_value=final_value,
        contributions=contributions,
        withdrawals=withdrawals,
        income=income_total,
        simple_return=simple_return,
        twr=twr,
        annualized_twr=annualized_twr,
        xirr=_xirr_of(snapshots, flows, income),
        volatility=volatility,
        max_drawdown=max_drawdown if returns else None,
        sharpe=sharpe,
        sortino=sortino,
        periods=len(returns),
        periods_detail=periods,
    )


def _annualized_volatility(returns: list[float]) -> float | None:
    deviation = _stdev(returns)
    if deviation is None:
        return None
    return deviation * math.sqrt(MONTHS_PER_YEAR)


def _annualized_downside(returns: list[float]) -> float | None:
    """Annualised downside deviation with a zero target."""
    if not returns:
        return None
    squares = [min(value, 0.0) ** 2 for value in returns]
    return math.sqrt(sum(squares) / len(squares)) * math.sqrt(MONTHS_PER_YEAR)


def _xirr_of(
    snapshots: list[Snapshot],
    flows: list[CashFlow],
    income: list[CashFlow],
) -> float | None:
    """XIRR of the window: the initial value counts as money invested at start."""
    start_date, initial_value = snapshots[0]
    end_date, final_value = snapshots[-1]

    investor_flows: list[tuple[date, float]] = [(start_date, -float(initial_value))]
    investor_flows.extend(
        (flow_date, -float(amount))
        for flow_date, amount in flows
        if start_date < flow_date <= end_date
    )
    investor_flows.extend(
        (income_date, float(amount))
        for income_date, amount in income
        if start_date < income_date <= end_date
    )
    investor_flows.append((end_date, float(final_value)))
    return xirr(investor_flows)
