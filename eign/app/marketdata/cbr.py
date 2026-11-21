from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from xml.etree import ElementTree

from .base import TextFetcher
from .http import fetch_text

DEFAULT_URL = "https://www.cbr.ru/scripts/XML_daily.asp"

# CBR quotes a currency per `Nominal` units, e.g. 100 KZT.
@dataclass(frozen=True)
class CbrRates:
    """Currency rates expressed in roubles per one unit."""

    date: date
    rates: dict[str, Decimal]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        return None


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value.replace(",", ".").strip())
    except ArithmeticError:
        return None


def fetch_rates(*, fetcher: TextFetcher = fetch_text, base_url: str = DEFAULT_URL) -> CbrRates | None:
    """Fetch the official CBR daily rates and normalise them per unit."""
    payload = fetcher(base_url)
    root = ElementTree.fromstring(payload)
    rate_date = _parse_date(root.attrib.get("Date")) or date.today()

    rates: dict[str, Decimal] = {"RUB": Decimal(1)}
    for valute in root.findall("Valute"):
        code = (valute.findtext("CharCode") or "").strip().upper()
        nominal = _parse_decimal(valute.findtext("Nominal")) or Decimal(1)
        value = _parse_decimal(valute.findtext("Value"))
        if not code or value is None or nominal <= 0:
            continue
        rates[code] = value / nominal

    return CbrRates(date=rate_date, rates=rates) if len(rates) > 1 else None
