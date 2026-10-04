"""Unit tests for the payload-to-pandas conversion helpers."""

from __future__ import annotations

import pandas as pd

from app.routers.financials import _build_metrics, _build_ratios  # pyright: ignore[reportPrivateUsage]
from app.schemas import FinancialDataUpload


def _payload(
    metrics: dict[str, dict[str, float | None]] | None = None,
    ratios: dict[str, dict[str, float | None]] | None = None,
) -> FinancialDataUpload:
    return FinancialDataUpload(
        companyName="Sber",
        ticker="SBER",
        industryName="Banks",
        metrics=metrics or {},
        ratios=ratios or {},
    )


def test_build_metrics_basic() -> None:
    result = _build_metrics(_payload(metrics={"revenue": {"2023": 1000.0, "2024": 1200.0}}))
    assert set(result) == {"revenue"}
    assert result["revenue"].index.tolist() == [2023, 2024]
    assert result["revenue"].to_dict() == {2023: 1000.0, 2024: 1200.0}


def test_build_metrics_skips_none() -> None:
    result = _build_metrics(_payload(metrics={"net_profit": {"2023": 100.0, "2024": None}}))
    assert result["net_profit"].to_dict() == {2023: 100.0}


def test_build_metrics_empty_when_all_none() -> None:
    result = _build_metrics(_payload(metrics={"revenue": {"2023": None}}))
    assert result == {}


def test_build_ratios_basic() -> None:
    df = _build_ratios(_payload(ratios={
        "2023": {"icr": 3.2, "tata": 0.1},
        "2024": {"icr": 3.4},
    }))
    assert df.index.tolist() == [2023, 2024]
    assert set(df.columns) == {"icr", "tata"}
    assert df.loc[2023, "icr"] == 3.2
    assert pd.isna(df.loc[2024, "tata"])  # missing combination becomes NaN


def test_build_ratios_skips_none() -> None:
    df = _build_ratios(_payload(ratios={"2023": {"icr": None, "tata": 0.1}}))
    assert "icr" not in df.columns
    assert df.loc[2023, "tata"] == 0.1
