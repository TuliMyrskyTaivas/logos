"""Offline tests of the market data providers (recorded payloads)."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from app.marketdata import cbr, guldvegt, moex


class FakeFetcher:
    """Routes URLs to recorded payloads by substring."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        for fragment, payload in self._responses.items():
            if fragment in url:
                return payload if isinstance(payload, str) else json.dumps(payload)
        raise AssertionError(f"unexpected URL: {url}")


def _table(columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    return {"columns": columns, "data": rows}


def test_moex_share_price() -> None:
    fetcher = FakeFetcher(
        {
            "iss/securities.json?q=SBER": {
                "securities": _table(
                    ["secid", "isin", "is_traded"],
                    [["SBER", "RU0009029540", 1]],
                )
            },
            "/iss/securities/SBER.json": {
                "boards": _table(
                    ["secid", "boardid", "market", "engine", "is_traded", "is_primary", "currencyid", "unit"],
                    [["SBER", "TQBR", "shares", "stock", 1, 1, "RUB", "M"]],
                ),
                "description": _table(["name", "title", "value"], []),
            },
            "only=marketdata": {
                "marketdata": _table(
                    ["SECID", "LAST", "LCURRENTPRICE"], [["SBER", 286.24, 286.22]]
                )
            },
        }
    )

    quote = moex.fetch_quote("SBER", fetcher=fetcher)
    assert quote is not None
    assert quote.price == Decimal("286.24000000")
    assert quote.currency == "RUB"
    assert quote.source == "moex"


def test_moex_bond_price_is_converted_from_percent_of_face_value() -> None:
    fetcher = FakeFetcher(
        {
            "iss/securities.json?q=SU26238RMFS4": {
                "securities": _table(
                    ["secid", "isin", "is_traded"],
                    [["SU26238RMFS4", "RU000A1038V6", 1]],
                )
            },
            "/iss/securities/SU26238RMFS4.json": {
                "boards": _table(
                    ["secid", "boardid", "market", "engine", "is_traded", "is_primary", "currencyid", "unit"],
                    [["SU26238RMFS4", "TQOB", "bonds", "stock", 1, 1, "RUB", "%"]],
                ),
                "description": _table(
                    ["name", "title", "value"], [["FACEVALUE", "Номинал", 1000]]
                ),
            },
            "only=marketdata": {
                "marketdata": _table(
                    ["SECID", "LAST", "LCURRENTPRICE"], [["SU26238RMFS4", 50.633, 50.636]]
                )
            },
        }
    )

    quote = moex.fetch_quote("SU26238RMFS4", fetcher=fetcher)
    assert quote is not None
    assert quote.price == Decimal("506.33000000")


def test_moex_returns_none_for_an_unknown_instrument() -> None:
    fetcher = FakeFetcher(
        {"iss/securities.json?q=UNKNOWN": {"securities": _table(["secid", "is_traded"], [])}}
    )
    assert moex.fetch_quote("UNKNOWN", fetcher=fetcher) is None


def test_cbr_rates_are_normalised_per_unit() -> None:
    xml = """<?xml version="1.0" encoding="windows-1251"?>
    <ValCurs Date="21.11.2025" name="Foreign Currency Market">
      <Valute ID="R01235">
        <NumCode>840</NumCode>
        <CharCode>USD</CharCode>
        <Nominal>1</Nominal>
        <Name>Доллар США</Name>
        <Value>80,5000</Value>
      </Valute>
      <Valute ID="R01335">
        <NumCode>398</NumCode>
        <CharCode>KZT</CharCode>
        <Nominal>100</Nominal>
        <Name>Казахстанских тенге</Name>
        <Value>16,0000</Value>
      </Valute>
    </ValCurs>"""
    fetcher = FakeFetcher({"XML_daily": xml})

    rates = cbr.fetch_rates(fetcher=fetcher)
    assert rates is not None
    assert rates.date.isoformat() == "2025-11-21"
    assert rates.rates["RUB"] == Decimal(1)
    assert rates.rates["USD"] == Decimal("80.5")
    assert rates.rates["KZT"] == Decimal("0.16")


def test_guldvegt_uses_the_median_price_per_gram() -> None:
    payload: list[dict[str, Any]] = [
        {"metal": "gold", "weight": 100, "buyPrice": 650000, "currency": "RUB"},
        {"metal": "gold", "weight": 1, "buyPrice": 7000, "currency": "RUB"},
        {"metal": "silver", "weight": 100, "buyPrice": 9000, "currency": "RUB"},
    ]
    fetcher = FakeFetcher({"quotes/bullions": payload})

    quote = guldvegt.fetch_quote("XAU", base_url="http://guldvegt:9080", fetcher=fetcher)
    assert quote is not None
    assert quote.price == Decimal("6750")
    assert quote.currency == "RUB"
    assert quote.source == "guldvegt"


def test_guldvegt_ignores_unsupported_metals() -> None:
    fetcher = FakeFetcher({"quotes/bullions": []})
    assert (
        guldvegt.fetch_quote("XPT", base_url="http://guldvegt:9080", fetcher=fetcher)
        is None
    )
