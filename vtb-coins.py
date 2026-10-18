"""Fetch VTB investment gold coin sell and buyback prices."""

import gzip
import html
import json
import re
import urllib.request
from typing import TypedDict

API_URL = "https://www.vtb.ru/api/bff/api/v1/coin/list?page=1"
BUYBACK_URL = (
    "https://www.vtb.ru/personal/vklady-i-scheta/monety-iz-drag-metallov-v/"
)

PAYLOAD = {
    "filters": [
        {"id": "coinCountry", "values": ["Российские"]},
        {"id": "coinKind", "values": ["Инвестиционные"]},
        {"id": "coinMetal", "values": ["Золото"]},
    ]
}

HEADERS = {
    "Content-Type": "application/json",
    "Accept-Encoding": "gzip, deflate, zstd, br",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
}

CARD_MARKER = "card-layout-griddesktopstyles__Item"
NAME_RE = re.compile(r"<p[^>]*>([^<]+)</p>")
MASS_RE = re.compile(r"Масса — ([\d\s\u00a0]+(?:,\d+)?)\s*г")
BUYBACK_RE = re.compile(
    r">\s*([\d\s\u00a0]+?)\s*₽\s*</p>\s*</div>\s*<span[^>]*>\s*Цена выкупа"
)


class Buyback(TypedDict):
    name: str
    mass: float
    price: int


class CoinQuote(TypedDict, total=False):
    name: str
    mass: float
    price1: int
    buyback: int


def fetch(url: str, data: bytes | None = None, accept: str = "application/json") -> str:
    request = urllib.request.Request(
        url,
        data=data,
        headers={**HEADERS, "Accept": accept},
    )

    with urllib.request.urlopen(request) as response:
        raw = response.read()
        encoding = response.headers.get("Content-Encoding", "").lower()
        if encoding == "br":
            import brotli

            raw = brotli.decompress(raw)
        elif encoding == "gzip":
            raw = gzip.decompress(raw)

    return raw.decode("utf-8")


def parse_number(text: str) -> float:
    return float(re.sub(r"[\s\u00a0]", "", text).replace(",", "."))


def parse_buybacks(page: str) -> list[Buyback]:
    buybacks: list[Buyback] = []
    for card in page.split(CARD_MARKER)[1:]:
        name = NAME_RE.search(card)
        mass = MASS_RE.search(card)
        price = BUYBACK_RE.search(card)
        if not (name and mass and price):
            continue
        buybacks.append(
            {
                "name": html.unescape(name.group(1)).strip(),
                "mass": parse_number(mass.group(1)),
                "price": int(parse_number(price.group(1))),
            }
        )
    return buybacks


def main() -> None:
    parsed = json.loads(fetch(API_URL, json.dumps(PAYLOAD).encode("utf-8")))
    buybacks = parse_buybacks(fetch(BUYBACK_URL, accept="text/html"))

    available: dict[tuple[str, float], list[int]] = {}
    for buyback in buybacks:
        key = (buyback["name"], round(buyback["mass"], 3))
        available.setdefault(key, []).append(buyback["price"])

    coins: list[CoinQuote] = []
    for coin in parsed["coins"]:
        quote: CoinQuote = {
            "name": coin["name"],
            "mass": coin["mass"],
            "price1": coin["price1"],
        }
        prices = available.get((coin["name"], round(coin["mass"], 3)))
        if prices:
            quote["buyback"] = prices.pop(0)
        coins.append(quote)

    print(json.dumps(coins, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
