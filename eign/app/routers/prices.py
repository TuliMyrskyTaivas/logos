from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_frontend_db
from ..models import Price as PriceModel
from ..models import User as UserModel
from ..schemas import Price, PriceCreate, PriceInstrumentType

router = APIRouter(prefix="/prices", tags=["prices"])


def _to_api_price(row: PriceModel) -> Price:
    return Price(
        id=row.id,
        instrument=row.instrument,
        instrumentType=cast(PriceInstrumentType, row.instrument_type),
        source=row.source,
        priceDate=row.price_date,
        price=float(row.price),
        currency=row.currency,
    )


@router.post(
    "",
    response_model=Price,
    status_code=status.HTTP_201_CREATED,
    summary="Enter a quote manually",
)
def create_manual_price(
    payload: PriceCreate,
    _user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> Price:
    """Store a manual quote; it takes precedence over fetched quotes of that day."""
    instrument = payload.instrument.strip().upper()
    if not instrument:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="instrument must not be empty",
        )
    price_date = payload.priceDate or date.today()
    if price_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="priceDate must not be in the future",
        )

    row = session.execute(
        select(PriceModel).where(
            PriceModel.instrument == instrument,
            PriceModel.source == "manual",
            PriceModel.price_date == price_date,
        )
    ).scalar_one_or_none()

    if row is None:
        row = PriceModel(
            instrument=instrument,
            instrument_type=payload.instrumentType,
            source="manual",
            price_date=price_date,
            price=Decimal(str(payload.price)),
            currency=payload.currency,
        )
        session.add(row)
    else:
        row.instrument_type = payload.instrumentType
        row.price = Decimal(str(payload.price))
        row.currency = payload.currency

    session.commit()
    session.refresh(row)
    return _to_api_price(row)
