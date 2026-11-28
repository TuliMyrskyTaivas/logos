"""Portfolio valuation tests: prices, currencies and aggregation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient


def _summary(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get("/portfolio/summary", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_summary_uses_the_manual_position_price(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset_factory(name="SBER", quantity=10, currentPrice=250)

    summary = _summary(client, admin)
    assert summary["baseCurrency"] == "RUB"
    assert summary["totalValue"] == 2500.0
    assert summary["unpricedCount"] == 0

    position = summary["positions"][0]
    assert position["priced"] is True
    assert position["price"] == 250
    assert position["priceSource"] == "manual"
    assert position["valueBase"] == 2500.0

    assert summary["byClass"] == [
        {
            "assetClassId": 1,
            "assetClassCode": "EQUITY",
            "value": 2500.0,
            "weight": 1.0,
        }
    ]


def test_manual_quote_overrides_the_position_price(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset_factory(name="SBER", ticker="SBER", quantity=10, currentPrice=250)

    created = client.post(
        "/prices",
        headers=admin,
        json={"instrument": "sber", "instrumentType": "ticker", "price": 300},
    )
    assert created.status_code == 201
    assert created.json()["instrument"] == "SBER"
    assert created.json()["source"] == "manual"

    position = _summary(client, admin)["positions"][0]
    assert position["price"] == 300
    assert position["priceSource"] == "manual"
    assert position["valueBase"] == 3000.0


def test_future_manual_price_is_rejected(
    client: TestClient, admin: dict[str, str]
) -> None:
    response = client.post(
        "/prices",
        headers=admin,
        json={
            "instrument": "SBER",
            "instrumentType": "ticker",
            "price": 300,
            "priceDate": "2999-01-01",
        },
    )
    assert response.status_code == 422


def test_cash_is_valued_at_face_value(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset_factory(name="RUB account", assetClassId=4, unit="RUB", quantity=5000)

    summary = _summary(client, admin)
    assert summary["totalValue"] == 5000.0
    assert summary["positions"][0]["priceSource"] == "cash"


def test_unpriced_position_is_reported(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset_factory(name="SBER", ticker="SBER")

    summary = _summary(client, admin)
    assert summary["totalValue"] == 0.0
    assert summary["unpricedCount"] == 1
    assert summary["byClass"] == []

    position = summary["positions"][0]
    assert position["priced"] is False
    assert position["unpricedReason"] == "no_price"
    assert position["valueBase"] is None


def test_position_without_instrument_is_reported_separately(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset_factory(name="Something")

    position = _summary(client, admin)["positions"][0]
    assert position["unpricedReason"] == "no_instrument"


def test_foreign_currency_requires_a_rate(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset_factory(
        name="AAPL", quantity=10, currency="USD", currentPrice=10
    )

    without_rate = _summary(client, admin)
    assert without_rate["unpricedCount"] == 1
    assert without_rate["positions"][0]["unpricedReason"] == "no_rate"
    assert without_rate["positions"][0]["value"] == 100.0

    rate = client.post(
        "/prices",
        headers=admin,
        json={"instrument": "USD", "instrumentType": "currency", "price": 80},
    )
    assert rate.status_code == 201

    with_rate = _summary(client, admin)
    assert with_rate["unpricedCount"] == 0
    assert with_rate["totalValue"] == 8000.0


def test_class_weights_and_aggregation(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset_factory(name="SBER", quantity=10, currentPrice=300)
    asset_factory(name="RUB account", assetClassId=4, unit="RUB", quantity=1000)

    summary = _summary(client, admin)
    assert summary["totalValue"] == 4000.0
    by_class = {item["assetClassCode"]: item for item in summary["byClass"]}
    assert by_class["EQUITY"]["value"] == 3000.0
    assert by_class["EQUITY"]["weight"] == 0.75
    assert by_class["CASH"]["value"] == 1000.0
    assert by_class["CASH"]["weight"] == 0.25


def test_metal_base_currency_converts_the_portfolio(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    """A base currency in grams of gold must use the metal quote, not only CBR."""
    asset_factory(name="SBER", quantity=100, currentPrice=400)
    rate = client.post(
        "/prices",
        headers=admin,
        json={"instrument": "XAU", "instrumentType": "metal", "price": 8000},
    )
    assert rate.status_code == 201

    updated = client.patch("/auth/me", headers=admin, json={"baseCurrency": "XAU"})
    assert updated.status_code == 200
    assert updated.json()["baseCurrency"] == "XAU"

    summary = _summary(client, admin)
    assert summary["baseCurrency"] == "XAU"
    assert summary["unpricedCount"] == 0
    assert summary["totalValue"] == 5.0
    assert summary["positions"][0]["valueBase"] == 5.0
