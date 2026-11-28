from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .models import Asset as AssetModel
from .models import Price as PriceModel

CASH_CLASS_CODE = "CASH"
METAL_CLASS_CODE = "METAL"

# When several sources have a quote for the same day, a manual correction wins.
SOURCE_PRIORITY = {"manual": 0, "moex": 1, "guldvegt": 2, "cbr": 3}


@dataclass(frozen=True)
class Instrument:
    """Identifies something that has a price in the `prices` cache."""

    identifier: str
    instrument_type: str


@dataclass(frozen=True)
class ResolvedPrice:
    """The price used to value a position, with its provenance."""

    price: Decimal
    currency: str
    source: str
    price_date: date | None


def instrument_of(asset: AssetModel) -> Instrument | None:
    """Return the price-cache key of a position; cash has no instrument."""
    class_code = asset.asset_class.code
    if class_code == CASH_CLASS_CODE:
        return None
    if class_code == METAL_CLASS_CODE and asset.metal_code:
        return Instrument(asset.metal_code.strip().upper(), "metal")
    if asset.ticker:
        return Instrument(asset.ticker.strip().upper(), "ticker")
    if asset.isin:
        return Instrument(asset.isin.strip().upper(), "isin")
    return None


def _is_better(candidate: PriceModel, current: PriceModel | None) -> bool:
    if current is None:
        return True
    if candidate.price_date != current.price_date:
        return candidate.price_date > current.price_date
    return SOURCE_PRIORITY.get(candidate.source, 9) < SOURCE_PRIORITY.get(
        current.source, 9
    )


def latest_market_prices(
    session: Session, identifiers: set[str], *, as_of: date
) -> dict[str, PriceModel]:
    """Return the newest quote per instrument, ignoring future dates."""
    if not identifiers:
        return {}
    rows = session.execute(
        select(PriceModel).where(
            PriceModel.instrument.in_(identifiers),
            PriceModel.instrument_type != "currency",
            PriceModel.price_date <= as_of,
        )
    ).scalars().all()

    latest: dict[str, PriceModel] = {}
    for row in rows:
        if _is_better(row, latest.get(row.instrument)):
            latest[row.instrument] = row
    return latest


def resolve_price(
    asset: AssetModel,
    prices: dict[str, PriceModel],
) -> ResolvedPrice | None:
    """Pick the price for a position: market cache first, then manual asset price."""
    if asset.asset_class.code == CASH_CLASS_CODE:
        return ResolvedPrice(Decimal(1), asset.currency, "cash", None)

    instrument = instrument_of(asset)
    if instrument is not None:
        row = prices.get(instrument.identifier)
        if row is not None:
            return ResolvedPrice(row.price, row.currency, row.source, row.price_date)

    if asset.current_price is not None:
        return ResolvedPrice(asset.current_price, asset.currency, "manual", None)
    return None


def convert_to_base(
    value: Decimal, currency: str, base_currency: str, rates: dict[str, Decimal]
) -> Decimal | None:
    """Convert an amount into the portfolio base currency using CBR rates."""
    if currency == base_currency:
        return value
    rate = rates.get(currency)
    base_rate = rates.get(base_currency)
    if rate is None or base_rate is None or base_rate == 0:
        return None
    return value * rate / base_rate


def latest_rate_map(
    session: Session, codes: set[str], *, as_of: date
) -> dict[str, Decimal]:
    """Roubles per unit for fiat codes and per gram for metals.

    Metals are priced per gram by the market data layer, so a goal expressed
    in XAU means grams of gold.
    """
    rates: dict[str, Decimal] = {"RUB": Decimal(1)}
    if not codes:
        return rates

    rows = session.execute(
        select(PriceModel).where(
            PriceModel.instrument.in_(codes),
            PriceModel.instrument_type.in_(("currency", "metal")),
            PriceModel.price_date <= as_of,
        )
    ).scalars().all()

    latest: dict[str, PriceModel] = {}
    for row in rows:
        if _is_better(row, latest.get(row.instrument)):
            latest[row.instrument] = row

    for code, row in latest.items():
        if row.instrument_type == "currency":
            rates[code] = row.price
        elif row.currency == "RUB":
            rates[code] = row.price
        else:
            fiat_rate = rates.get(row.currency)
            if fiat_rate is not None:
                rates[code] = row.price * fiat_rate
    return rates


@dataclass(frozen=True)
class PositionValuation:
    """One position with the price and values used to assess it."""

    asset: AssetModel
    price: ResolvedPrice | None
    value: Decimal | None
    value_base: Decimal | None
    unpriced_reason: str | None

    @property
    def priced(self) -> bool:
        return self.value_base is not None


@dataclass(frozen=True)
class PortfolioValuation:
    """A whole portfolio valued at a date."""

    base_currency: str
    as_of: date
    total: Decimal
    by_class: dict[int, tuple[str, Decimal]]
    positions: list[PositionValuation]
    unpriced_count: int


def value_portfolio(
    session: Session,
    owner_id: int,
    base_currency: str,
    as_of: date,
) -> PortfolioValuation:
    """Value all positions of a user at the latest prices available by `as_of`.

    Shared by the summary endpoint and the monthly snapshot job so both use
    exactly the same rules.
    """
    base = (base_currency or "RUB").strip().upper()
    assets = session.execute(
        select(AssetModel)
        .options(joinedload(AssetModel.asset_class))
        .where(AssetModel.owner_id == owner_id)
        .order_by(AssetModel.id)
    ).scalars().all()

    identifiers = {
        instrument.identifier
        for asset in assets
        if (instrument := instrument_of(asset)) is not None
    }
    prices = latest_market_prices(session, identifiers, as_of=as_of)

    currencies = {asset.currency.strip().upper() for asset in assets}
    currencies.add(base)
    # `latest_rate_map` knows both CBR fiat rates and metal gram prices, so a
    # metal base currency (XAU) and metal-denominated positions both convert.
    rates = latest_rate_map(session, currencies - {"RUB"}, as_of=as_of)

    positions: list[PositionValuation] = []
    by_class: dict[int, tuple[str, Decimal]] = {}
    total = Decimal(0)
    unpriced_count = 0

    for asset in assets:
        resolved = resolve_price(asset, prices)
        value: Decimal | None = None
        value_base: Decimal | None = None
        reason: str | None = None

        if resolved is None:
            reason = "no_instrument" if instrument_of(asset) is None else "no_price"
        else:
            value = asset.quantity * resolved.price
            value_base = convert_to_base(
                value, resolved.currency.strip().upper(), base, rates
            )
            if value_base is None:
                reason = "no_rate"

        if value_base is None:
            unpriced_count += 1
        else:
            total += value_base
            class_code, class_total = by_class.get(
                asset.asset_class_id, (asset.asset_class.code, Decimal(0))
            )
            by_class[asset.asset_class_id] = (class_code, class_total + value_base)

        positions.append(
            PositionValuation(
                asset=asset,
                price=resolved,
                value=value,
                value_base=value_base,
                unpriced_reason=reason,
            )
        )

    return PortfolioValuation(
        base_currency=base,
        as_of=as_of,
        total=total,
        by_class=by_class,
        positions=positions,
        unpriced_count=unpriced_count,
    )
