"""Pure-function tests of the performance metrics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.performance import compute_performance, empty_performance, xirr

JAN = date(2026, 1, 1)
FEB = date(2026, 2, 1)
MAR = date(2026, 3, 1)


def test_empty_portfolio_has_no_metrics() -> None:
    result = empty_performance()
    assert result.twr is None
    assert result.periods == 0
    assert result.periods_detail == []


def test_twr_is_corrected_for_contributions() -> None:
    snapshots = [(JAN, Decimal(1000)), (FEB, Decimal(1650))]
    flows = [(date(2026, 1, 15), Decimal(500))]

    result = compute_performance(snapshots, flows)

    assert result.twr == pytest.approx(0.15)
    assert result.contributions == Decimal(500)
    assert result.withdrawals == Decimal(0)
    assert result.simple_return == pytest.approx(0.1)
    assert result.periods == 1
    assert result.periods_detail[0].return_pct == pytest.approx(0.15)


def test_period_without_starting_value_is_skipped() -> None:
    snapshots = [(JAN, Decimal(0)), (FEB, Decimal(1000))]
    flows = [(date(2026, 1, 10), Decimal(1000))]

    result = compute_performance(snapshots, flows)

    assert result.periods == 0
    assert result.twr is None
    assert result.contributions == Decimal(1000)
    assert result.periods_detail[0].return_pct is None


def test_risk_metrics_match_a_known_series() -> None:
    # Returns: +10 % and -5 %.
    snapshots = [(JAN, Decimal(1000)), (FEB, Decimal(1100)), (MAR, Decimal(1045))]

    result = compute_performance(snapshots, [])

    assert result.twr == pytest.approx(0.045)
    assert result.volatility == pytest.approx(0.367423, rel=1e-5)
    assert result.max_drawdown == pytest.approx(-0.05)
    assert result.sharpe == pytest.approx(0.816497, rel=1e-5)
    assert result.sortino == pytest.approx(2.44949, rel=1e-5)


def test_risk_free_rate_lowers_sharpe() -> None:
    snapshots = [(JAN, Decimal(1000)), (FEB, Decimal(1100)), (MAR, Decimal(1045))]

    base = compute_performance(snapshots, [])
    with_rate = compute_performance(snapshots, [], risk_free_rate=0.1)

    assert base.sharpe is not None and with_rate.sharpe is not None
    assert with_rate.sharpe < base.sharpe


def test_income_increases_period_return() -> None:
    # 1050 at the end plus 50 of dividends received = 10 % return.
    snapshots = [(JAN, Decimal(1000)), (FEB, Decimal(1050))]
    income = [(FEB, Decimal(50))]

    result = compute_performance(snapshots, [], income=income)

    assert result.twr == pytest.approx(0.10)
    assert result.simple_return == pytest.approx(0.10)
    assert result.income == Decimal(50)
    assert result.xirr is not None


def test_income_is_not_a_capital_contribution() -> None:
    snapshots = [(JAN, Decimal(1000)), (FEB, Decimal(1000))]
    income = [(FEB, Decimal(100))]

    result = compute_performance(snapshots, [], income=income)

    assert result.contributions == Decimal(0)
    assert result.twr == pytest.approx(0.10)


def test_xirr_of_a_single_year_investment() -> None:
    flows = [(date(2025, 1, 1), -1000.0), (date(2026, 1, 1), 1100.0)]
    assert xirr(flows) == pytest.approx(0.10, rel=1e-4)


def test_xirr_is_none_without_both_directions() -> None:
    assert xirr([]) is None
    assert xirr([(JAN, -1000.0)]) is None
    assert xirr([(JAN, 1000.0)]) is None
