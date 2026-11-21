"""Background price refresh tests with stubbed providers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.prices import RefreshResult, refresh_prices
from app.marketdata.base import PriceQuote
from app.marketdata.cbr import CbrRates
from app.models import Price

TRADE_DATE = date(2026, 11, 21)


def _stub_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def moex_quote(identifier: str, **_: Any) -> PriceQuote | None:
        if identifier == "SBER":
            return PriceQuote(Decimal("286.24"), "RUB", "moex")
        return None

    def guldvegt_quote(metal_code: str, **_: Any) -> PriceQuote | None:
        if metal_code == "XAU":
            return PriceQuote(Decimal("6750"), "RUB", "guldvegt")
        return None

    def cbr_rates(**_: Any) -> CbrRates:
        return CbrRates(
            date=TRADE_DATE, rates={"RUB": Decimal(1), "USD": Decimal("80")}
        )

    monkeypatch.setattr("app.jobs.prices.moex.fetch_quote", moex_quote)
    monkeypatch.setattr("app.jobs.prices.guldvegt.fetch_quote", guldvegt_quote)
    monkeypatch.setattr("app.jobs.prices.cbr.fetch_rates", cbr_rates)


def _refresh(**_: Any) -> RefreshResult:
    return refresh_prices(today=TRADE_DATE, fetcher=lambda _url: "")


def test_refresh_stores_quotes_and_rates(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
    backend_scope: Any,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_factory(name="SBER", ticker="SBER")
    asset_factory(name="Gold", assetClassId=5, unit="g", metalCode="XAU")
    asset_factory(name="USD account", assetClassId=4, unit="RUB", currency="USD")
    _stub_providers(monkeypatch)

    result = _refresh()
    assert result.stored == 2
    assert result.rates == 1
    assert result.failed == 0

    rows = {
        (row.instrument, row.source): row
        for row in db_session.execute(select(Price)).scalars().all()
    }
    assert rows[("SBER", "moex")].price == Decimal("286.24000000")
    assert rows[("XAU", "guldvegt")].price == Decimal("6750.00000000")
    assert rows[("USD", "cbr")].instrument_type == "currency"
    assert rows[("USD", "cbr")].currency == "RUB"
    assert rows[("USD", "cbr")].price == Decimal("80.00000000")


def test_refresh_is_idempotent_within_a_day(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
    backend_scope: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_factory(name="SBER", ticker="SBER")
    _stub_providers(monkeypatch)

    assert _refresh().stored == 1
    second = _refresh()
    assert second.stored == 0
    assert second.rates == 0


def test_manual_quote_is_not_overwritten(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
    backend_scope: Any,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_factory(name="SBER", ticker="SBER")
    _stub_providers(monkeypatch)

    client.post(
        "/prices",
        headers=admin,
        json={
            "instrument": "SBER",
            "instrumentType": "ticker",
            "price": 999,
            "priceDate": TRADE_DATE.isoformat(),
        },
    )

    result = _refresh()
    assert result.stored == 0
    assert result.skipped_manual == 1

    price = db_session.execute(
        select(Price).where(Price.instrument == "SBER")
    ).scalar_one()
    assert price.source == "manual"
    assert price.price == Decimal("999.00000000")


def test_provider_failure_does_not_abort_the_run(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
    backend_scope: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_factory(name="BROKEN", ticker="BROKEN")
    asset_factory(name="SBER", ticker="SBER")

    def failing_moex(identifier: str, **_: Any) -> PriceQuote | None:
        if identifier == "BROKEN":
            raise TimeoutError("upstream is down")
        return PriceQuote(Decimal("286.24"), "RUB", "moex")

    monkeypatch.setattr("app.jobs.prices.moex.fetch_quote", failing_moex)
    def rates_stub(**_: Any) -> CbrRates:
        return CbrRates(date=TRADE_DATE, rates={"RUB": Decimal(1)})

    monkeypatch.setattr("app.jobs.prices.cbr.fetch_rates", rates_stub)

    result = _refresh()
    assert result.stored == 1
    assert result.failed == 1
