from __future__ import annotations

import json
from decimal import Decimal
from statistics import median
from typing import Any, cast

from .base import PriceQuote, TextFetcher
from .http import fetch_text

# ISO 4217 metal codes mapped to the gûldvegt quote names.
METAL_NAMES = {"XAU": "gold", "XAG": "silver"}


def fetch_quote(
    metal_code: str,
    *,
    base_url: str,
    fetcher: TextFetcher = fetch_text,
) -> PriceQuote | None:
    """Return the price of one gram of a metal, or None.

    Bullion quotes come per vendor and per bar weight; the median price per
    gram is used so a single outlier vendor does not skew the valuation. The
    buyout price is taken because it is what the holder would receive.
    """
    metal = METAL_NAMES.get(metal_code.strip().upper())
    if metal is None:
        return None

    payload: Any = json.loads(fetcher(f"{base_url.rstrip('/')}/quotes/bullions"))
    if not isinstance(payload, list):
        return None
    quotes = cast(list[Any], payload)

    prices_per_gram: list[float] = []
    currency = "RUB"
    for quote in quotes:
        if not isinstance(quote, dict):
            continue
        record = cast(dict[str, Any], quote)
        if str(record.get("metal") or "").lower() != metal:
            continue
        try:
            weight = float(record.get("weight") or 0)
            buy_price = float(record.get("buyPrice") or 0)
        except (TypeError, ValueError):
            continue
        if weight <= 0 or buy_price <= 0:
            continue
        prices_per_gram.append(buy_price / weight)
        currency = str(record.get("currency") or currency)

    if not prices_per_gram:
        return None

    return PriceQuote(
        price=Decimal(str(round(median(prices_per_gram), 8))),
        currency=currency,
        source="guldvegt",
    )
