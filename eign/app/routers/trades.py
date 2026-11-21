from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_frontend_db
from ..models import Asset as AssetModel
from ..models import Trade as TradeModel
from ..models import User as UserModel
from ..schemas import Trade, TradeCreate, TradeType, TradeUpdate

router = APIRouter(prefix="/trades", tags=["trades"])


def to_api_trade(trade: TradeModel) -> Trade:
    """Convert the ORM trade into the API representation."""
    return Trade(
        id=trade.id,
        assetId=trade.asset_id,
        tradeType=cast(TradeType, trade.trade_type),
        tradeDate=trade.trade_date,
        quantity=float(trade.quantity),
        price=float(trade.price),
        fee=float(trade.fee),
        currency=trade.currency,
        note=trade.note,
        createdAt=trade.created_at,
    )


def _format_quantity(value: Decimal) -> str:
    """Render a quantity without insignificant trailing zeros."""
    return format(value.normalize(), "f")


def recalculate_position(session: Session, asset: AssetModel) -> None:
    """Rebuild position quantity and average cost from the trade history.

    Trades are replayed in chronological order using weighted average cost:
    buys increase the cost basis (including commission), sells remove a
    proportional part of it, so the average price is unchanged by a sale.
    """
    trades = session.execute(
        select(TradeModel)
        .where(TradeModel.asset_id == asset.id)
        .order_by(TradeModel.trade_date, TradeModel.id)
    ).scalars().all()

    quantity = Decimal("0")
    cost = Decimal("0")
    for trade in trades:
        if trade.trade_type == "BUY":
            quantity += trade.quantity
            cost += trade.quantity * trade.price + trade.fee
            continue

        if trade.quantity > quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Trade {trade.id} sells {_format_quantity(trade.quantity)} units, "
                    f"but only {_format_quantity(quantity)} are held at that moment"
                ),
            )
        cost -= cost * trade.quantity / quantity if quantity else Decimal("0")
        quantity -= trade.quantity
        if quantity == 0:
            cost = Decimal("0")

    asset.quantity = quantity
    asset.avg_purchase_price = cost / quantity if quantity > 0 else None


def _get_owned_asset(session: Session, owner_id: int, asset_id: int) -> AssetModel:
    asset = session.execute(
        select(AssetModel).where(
            AssetModel.id == asset_id, AssetModel.owner_id == owner_id
        )
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    return asset


def _get_owned_trade(session: Session, owner_id: int, trade_id: int) -> TradeModel:
    trade = session.execute(
        select(TradeModel).where(
            TradeModel.id == trade_id, TradeModel.owner_id == owner_id
        )
    ).scalar_one_or_none()
    if trade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found"
        )
    return trade


def _resolve_currency(asset: AssetModel, currency: str | None) -> str:
    """Trades are recorded in the position currency; mixed currencies are not supported yet."""
    if currency is None:
        return asset.currency
    if currency != asset.currency:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Trade currency {currency} does not match the position "
                f"currency {asset.currency}"
            ),
        )
    return currency


@router.get("", response_model=list[Trade], summary="List trades")
def list_trades(
    assetId: int | None = None,
    tradeType: TradeType | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> list[Trade]:
    """Return the current user's trades, newest first."""
    stmt = (
        select(TradeModel)
        .where(TradeModel.owner_id == user.id)
        .order_by(TradeModel.trade_date.desc(), TradeModel.id.desc())
    )
    if assetId is not None:
        stmt = stmt.where(TradeModel.asset_id == assetId)
    if tradeType is not None:
        stmt = stmt.where(TradeModel.trade_type == tradeType)
    if dateFrom is not None:
        stmt = stmt.where(TradeModel.trade_date >= dateFrom)
    if dateTo is not None:
        stmt = stmt.where(TradeModel.trade_date <= dateTo)
    trades = session.execute(stmt).scalars().all()
    return [to_api_trade(trade) for trade in trades]


@router.post(
    "", response_model=Trade, status_code=status.HTTP_201_CREATED, summary="Register a trade"
)
def create_trade(
    payload: TradeCreate,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> Trade:
    """Register a buy or sell and recalculate the position."""
    asset = _get_owned_asset(session, user.id, payload.assetId)
    currency = _resolve_currency(asset, payload.currency)

    trade = TradeModel(
        owner_id=user.id,
        asset=asset,
        trade_type=payload.tradeType,
        trade_date=payload.tradeDate,
        quantity=Decimal(str(payload.quantity)),
        price=Decimal(str(payload.price)),
        fee=Decimal(str(payload.fee)),
        currency=currency,
        note=payload.note,
    )
    session.add(trade)
    session.flush()

    recalculate_position(session, asset)
    asset.current_price = trade.price

    session.commit()
    session.refresh(trade)
    return to_api_trade(trade)


@router.patch("/{tradeId}", response_model=Trade, summary="Correct a trade")
def update_trade(
    tradeId: int,
    payload: TradeUpdate,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> Trade:
    """Correct a trade; the whole position is recalculated afterwards."""
    trade = _get_owned_trade(session, user.id, tradeId)
    asset = _get_owned_asset(session, user.id, trade.asset_id)
    data = payload.model_dump(exclude_unset=True)

    if "currency" in data and data["currency"] is not None:
        trade.currency = _resolve_currency(asset, data["currency"])
    if "tradeType" in data and data["tradeType"] is not None:
        trade.trade_type = data["tradeType"]
    if "tradeDate" in data and data["tradeDate"] is not None:
        trade.trade_date = data["tradeDate"]
    if "quantity" in data and data["quantity"] is not None:
        trade.quantity = Decimal(str(data["quantity"]))
    if "price" in data and data["price"] is not None:
        trade.price = Decimal(str(data["price"]))
    if "fee" in data and data["fee"] is not None:
        trade.fee = Decimal(str(data["fee"]))
    if "note" in data:
        trade.note = data["note"]

    session.flush()
    recalculate_position(session, asset)

    session.commit()
    session.refresh(trade)
    return to_api_trade(trade)


@router.delete("/{tradeId}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a trade")
def delete_trade(
    tradeId: int,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> None:
    """Delete a trade and recalculate the position from the remaining ones."""
    trade = _get_owned_trade(session, user.id, tradeId)
    asset = _get_owned_asset(session, user.id, trade.asset_id)

    session.delete(trade)
    session.flush()
    recalculate_position(session, asset)
    session.commit()
