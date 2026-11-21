from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..config import Settings, get_settings
from ..database import backend_session_scope
from ..marketdata import cbr, guldvegt, moex
from ..marketdata.base import PriceQuote, TextFetcher
from ..marketdata.http import make_fetcher
from ..models import Asset as AssetModel
from ..models import Price as PriceModel
from ..models import User as UserModel
from ..valuation import Instrument, instrument_of

logger = logging.getLogger("eign.jobs.prices")


@dataclass
class RefreshResult:
    """Summary of one price refresh run."""

    instruments: int = 0
    stored: int = 0
    skipped_manual: int = 0
    failed: int = 0
    rates: int = 0


def _fetch_quote(
    instrument: Instrument, fetcher: TextFetcher, settings: Settings
) -> PriceQuote | None:
    if instrument.instrument_type == "metal":
        return guldvegt.fetch_quote(
            instrument.identifier, base_url=settings.guldvegt_url, fetcher=fetcher
        )
    return moex.fetch_quote(
        instrument.identifier, fetcher=fetcher, base_url=settings.moex_url
    )


def _has_manual_price(session: Session, instrument: str, price_date: date) -> bool:
    return (
        session.execute(
            select(PriceModel.id)
            .where(
                PriceModel.instrument == instrument,
                PriceModel.source == "manual",
                PriceModel.price_date == price_date,
            )
            .limit(1)
        ).first()
        is not None
    )


def _store(
    session: Session, instrument: Instrument, quote: PriceQuote, price_date: date
) -> bool:
    exists = session.execute(
        select(PriceModel.id)
        .where(
            PriceModel.instrument == instrument.identifier,
            PriceModel.source == quote.source,
            PriceModel.price_date == price_date,
        )
        .limit(1)
    ).first()
    if exists is not None:
        return False

    session.add(
        PriceModel(
            instrument=instrument.identifier,
            instrument_type=instrument.instrument_type,
            source=quote.source,
            price_date=price_date,
            price=quote.price,
            currency=quote.currency,
        )
    )
    session.flush()
    return True


def _collect_instruments(assets: Sequence[AssetModel]) -> list[Instrument]:
    instruments: dict[Instrument, None] = {}
    for asset in assets:
        instrument = instrument_of(asset)
        if instrument is not None:
            instruments.setdefault(instrument, None)
    return list(instruments)


def refresh_prices(
    *,
    today: date | None = None,
    fetcher: TextFetcher | None = None,
    settings: Settings | None = None,
) -> RefreshResult:
    """Fetch quotes for every instrument used by positions and cache them.

    Runs under the `eign_backend` role: it may write `prices` but not the
    positions themselves. Manual quotes entered for the same day are never
    overwritten.
    """
    settings = settings or get_settings()
    fetcher = fetcher or make_fetcher(settings.marketdata_timeout)
    price_date = today or date.today()
    result = RefreshResult()

    with backend_session_scope() as session:
        assets = session.execute(
            select(AssetModel).options(joinedload(AssetModel.asset_class))
        ).scalars().all()
        instruments = _collect_instruments(assets)
        result.instruments = len(instruments)

        for instrument in instruments:
            try:
                quote = _fetch_quote(instrument, fetcher, settings)
            except Exception as exc:  # noqa: BLE001 - one provider must not stop the run
                logger.warning(
                    "price fetch failed for %s (%s): %s",
                    instrument.identifier,
                    instrument.instrument_type,
                    exc,
                )
                result.failed += 1
                continue

            if quote is None:
                logger.info(
                    "no quote for %s (%s)",
                    instrument.identifier,
                    instrument.instrument_type,
                )
                result.failed += 1
                continue

            if _has_manual_price(session, instrument.identifier, price_date):
                result.skipped_manual += 1
                continue

            if _store(session, instrument, quote, price_date):
                result.stored += 1

        currencies = {asset.currency.upper() for asset in assets}
        currencies |= {
            code.upper()
            for code in session.execute(select(UserModel.base_currency)).scalars()
            if code
        }
        currencies.discard("RUB")
        if currencies:
            try:
                cbr_rates = cbr.fetch_rates(fetcher=fetcher, base_url=settings.cbr_url)
            except Exception as exc:  # noqa: BLE001
                logger.warning("CBR rates fetch failed: %s", exc)
                cbr_rates = None

            if cbr_rates is not None:
                for code in sorted(currencies):
                    rate = cbr_rates.rates.get(code)
                    if rate is None:
                        logger.info("CBR has no rate for %s", code)
                        continue
                    if _has_manual_price(session, code, cbr_rates.date):
                        result.skipped_manual += 1
                        continue
                    quote = PriceQuote(price=rate, currency="RUB", source="cbr")
                    if _store(session, Instrument(code, "currency"), quote, cbr_rates.date):
                        result.rates += 1

    logger.info(
        "price refresh: instruments=%d stored=%d rates=%d skipped_manual=%d failed=%d",
        result.instruments,
        result.stored,
        result.rates,
        result.skipped_manual,
        result.failed,
    )
    return result
