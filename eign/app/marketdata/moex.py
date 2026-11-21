from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast
from urllib.parse import quote

from .base import PriceQuote, TextFetcher
from .http import fetch_text

DEFAULT_BASE_URL = "https://iss.moex.com"

# Percentage-priced instruments (bonds) are quoted in percent of the face value.
PERCENT_UNIT = "%"


@dataclass(frozen=True)
class Board:
    """A MOEX trading board of a security."""

    secid: str
    boardid: str
    engine: str
    market: str
    unit: str
    currency: str


def _table(payload: object, name: str) -> tuple[list[str], list[list[Any]]]:
    """Return the (columns, rows) of one ISS table."""
    if not isinstance(payload, dict):
        return [], []
    table = cast(dict[str, Any], payload).get(name)
    if not isinstance(table, dict):
        return [], []
    table_data = cast(dict[str, Any], table)
    columns_raw = table_data.get("columns")
    rows_raw = table_data.get("data")
    columns = (
        [str(column) for column in cast(list[Any], columns_raw)]
        if isinstance(columns_raw, list)
        else []
    )
    rows = (
        [cast(list[Any], row) for row in cast(list[Any], rows_raw) if isinstance(row, list)]
        if isinstance(rows_raw, list)
        else []
    )
    return columns, rows


def _records(payload: Any, name: str) -> list[dict[str, Any]]:
    columns, rows = _table(payload, name)
    return [dict(zip(columns, row, strict=False)) for row in rows]


def resolve_secid(identifier: str, fetcher: TextFetcher, base_url: str) -> str | None:
    """Find the MOEX security code for a ticker or an ISIN."""
    url = (
        f"{base_url}/iss/securities.json?q={quote(identifier)}"
        "&iss.meta=off&iss.only=securities"
    )
    records = _records(json.loads(fetcher(url)), "securities")
    wanted = identifier.strip().upper()
    traded = [record for record in records if record.get("is_traded") == 1]
    for record in traded:
        if str(record.get("isin") or "").upper() == wanted:
            return str(record["secid"])
        if str(record.get("secid") or "").upper() == wanted:
            return str(record["secid"])
    return str(traded[0]["secid"]) if traded else None


def _pick_board(boards: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prefer the primary trading board, otherwise the first traded one."""
    for board in boards:
        if board.get("is_primary") == 1 and board.get("is_traded") == 1:
            return board
    for board in boards:
        if board.get("is_traded") == 1:
            return board
    return None


def _face_value(description: list[dict[str, Any]]) -> Decimal | None:
    for record in description:
        if record.get("name") == "FACEVALUE":
            try:
                return Decimal(str(record.get("value")))
            except (ArithmeticError, ValueError):
                return None
    return None


def _market_price(marketdata: list[dict[str, Any]]) -> Decimal | None:
    if not marketdata:
        return None
    row = marketdata[0]
    for field in ("LAST", "LCURRENTPRICE", "MARKETPRICE"):
        value = row.get(field)
        if value is None:
            continue
        try:
            price = Decimal(str(value))
        except (ArithmeticError, ValueError):
            continue
        if price > 0:
            return price
    return None


def fetch_quote(
    identifier: str,
    *,
    fetcher: TextFetcher = fetch_text,
    base_url: str = DEFAULT_BASE_URL,
) -> PriceQuote | None:
    """Return the last known price of a MOEX security, or None.

    Bonds are quoted in percent of the face value, so the result is converted
    to a price per unit in the board currency.
    """
    secid = resolve_secid(identifier, fetcher, base_url)
    if secid is None:
        return None

    details = json.loads(
        fetcher(
            f"{base_url}/iss/securities/{quote(secid)}.json"
            "?iss.meta=off&iss.only=boards,description"
        )
    )
    board_row = _pick_board(_records(details, "boards"))
    if board_row is None:
        return None

    board = Board(
        secid=str(board_row["secid"]),
        boardid=str(board_row["boardid"]),
        engine=str(board_row.get("engine") or "stock"),
        market=str(board_row.get("market") or "shares"),
        unit=str(board_row.get("unit") or ""),
        currency=str(board_row.get("currencyid") or "RUB"),
    )

    marketdata = _records(
        json.loads(
            fetcher(
                f"{base_url}/iss/engines/{quote(board.engine)}/markets/{quote(board.market)}"
                f"/boards/{quote(board.boardid)}/securities/{quote(board.secid)}.json"
                "?iss.meta=off&iss.only=marketdata"
            )
        ),
        "marketdata",
    )
    price = _market_price(marketdata)
    if price is None:
        return None

    if board.unit == PERCENT_UNIT:
        face_value = _face_value(_records(details, "description"))
        if face_value is None:
            return None
        price = price * face_value / Decimal(100)

    return PriceQuote(
        price=price.quantize(Decimal("0.00000001")),
        currency=board.currency,
        source="moex",
    )
