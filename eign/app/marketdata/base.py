from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

# A fetcher returns the raw response body of a URL as text. Providers take it
# as a parameter so tests can feed recorded payloads instead of hitting the
# network.
TextFetcher = Callable[[str], str]


@dataclass(frozen=True)
class PriceQuote:
    """A price per unit of an instrument in its own currency."""

    price: Decimal
    currency: str
    source: str
