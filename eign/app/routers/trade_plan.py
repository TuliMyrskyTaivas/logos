from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_frontend_db
from ..models import Asset as AssetModel
from ..models import AssetClass as AssetClassModel
from ..models import Trade as TradeModel
from ..models import TradePlan as TradePlanModel
from ..models import User as UserModel
from ..schemas import PlanStatus, TradePlan, TradePlanCreate, TradePlanUpdate, TradeType

router = APIRouter(prefix="/trade-plan", tags=["trade-plan"])

TradeKey = tuple[date, str, int]


@dataclass(frozen=True)
class TradeTotals:
    """Trade aggregates of one user, keyed by (month, direction, asset/class id)."""

    quantity_by_asset: dict[TradeKey, Decimal]
    value_by_asset: dict[TradeKey, Decimal]
    value_by_class: dict[TradeKey, Decimal]


def month_start(value: date) -> date:
    """Normalise any date to the first day of its month."""
    return value.replace(day=1)


def _load_totals(session: Session, owner_id: int) -> TradeTotals:
    """Aggregate the user's trades per month, direction and target."""
    month = func.date_trunc("month", TradeModel.trade_date).label("month")

    by_asset = session.execute(
        select(
            month,
            TradeModel.trade_type,
            TradeModel.asset_id,
            func.sum(TradeModel.quantity),
            func.sum(TradeModel.quantity * TradeModel.price),
        )
        .where(TradeModel.owner_id == owner_id)
        .group_by(month, TradeModel.trade_type, TradeModel.asset_id)
    ).all()

    by_class = session.execute(
        select(
            month,
            TradeModel.trade_type,
            AssetModel.asset_class_id,
            func.sum(TradeModel.quantity * TradeModel.price),
        )
        .join(AssetModel, AssetModel.id == TradeModel.asset_id)
        .where(TradeModel.owner_id == owner_id)
        .group_by(month, TradeModel.trade_type, AssetModel.asset_class_id)
    ).all()

    quantity_by_asset: dict[TradeKey, Decimal] = {}
    value_by_asset: dict[TradeKey, Decimal] = {}
    for month_value, direction, asset_id, quantity, value in by_asset:
        key = (month_value.date(), direction, asset_id)
        quantity_by_asset[key] = Decimal(str(quantity or 0))
        value_by_asset[key] = Decimal(str(value or 0))

    value_by_class: dict[TradeKey, Decimal] = {
        (month_value.date(), direction, asset_class_id): Decimal(str(value or 0))
        for month_value, direction, asset_class_id, value in by_class
    }
    return TradeTotals(quantity_by_asset, value_by_asset, value_by_class)


def _filled(plan: TradePlanModel, totals: TradeTotals) -> Decimal:
    """Return the progress of the plan in its own target unit."""
    key_prefix = (plan.month, plan.direction)
    if plan.quantity is not None and plan.asset_id is not None:
        return totals.quantity_by_asset.get((*key_prefix, plan.asset_id), Decimal(0))
    if plan.asset_id is not None:
        return totals.value_by_asset.get((*key_prefix, plan.asset_id), Decimal(0))
    if plan.asset_class_id is not None:
        return totals.value_by_class.get((*key_prefix, plan.asset_class_id), Decimal(0))
    return Decimal(0)


def _effective_status(plan: TradePlanModel, filled: Decimal) -> str:
    """`executed` is derived: reaching the target is enough, overfulfilment is fine."""
    if plan.status == "cancelled":
        return "cancelled"
    target = plan.quantity if plan.quantity is not None else plan.amount
    if target is None:
        return "planned"
    return "executed" if filled >= target else "planned"


def to_api_plan(plan: TradePlanModel, totals: TradeTotals) -> TradePlan:
    """Convert the ORM plan row into the API representation."""
    filled = _filled(plan, totals)
    return TradePlan(
        id=plan.id,
        assetId=plan.asset_id,
        assetClassId=plan.asset_class_id,
        month=plan.month,
        direction=cast(TradeType, plan.direction),
        amount=float(plan.amount) if plan.amount is not None else None,
        quantity=float(plan.quantity) if plan.quantity is not None else None,
        filled=float(filled),
        status=cast(PlanStatus, _effective_status(plan, filled)),
        note=plan.note,
        createdAt=plan.created_at,
    )


def _get_owned_plan(session: Session, owner_id: int, plan_id: int) -> TradePlanModel:
    plan = session.execute(
        select(TradePlanModel).where(
            TradePlanModel.id == plan_id, TradePlanModel.owner_id == owner_id
        )
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trade plan entry not found"
        )
    return plan


def _resolve_target(
    session: Session,
    owner_id: int,
    asset_id: int | None,
    asset_class_id: int | None,
) -> tuple[int | None, int | None]:
    """Validate the planned target and return the effective (asset, class) ids."""
    if asset_id is None and asset_class_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Either assetId or assetClassId is required",
        )

    if asset_id is not None:
        asset = session.execute(
            select(AssetModel).where(
                AssetModel.id == asset_id, AssetModel.owner_id == owner_id
            )
        ).scalar_one_or_none()
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
            )
        if asset_class_id is not None and asset_class_id != asset.asset_class_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="assetClassId does not match the asset's class",
            )
        return asset.id, asset.asset_class_id

    if session.get(AssetClassModel, asset_class_id) is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset class {asset_class_id} does not exist",
        )
    return None, asset_class_id


def _validate_target(
    asset_id: int | None, amount: Decimal | None, quantity: Decimal | None
) -> None:
    """A plan is expressed either in money or in units — never in both."""
    if (amount is None) == (quantity is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Exactly one of amount or quantity is required",
        )
    if quantity is not None and asset_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="quantity requires assetId",
        )


@router.get("", response_model=list[TradePlan], summary="List planned trades")
def list_trade_plan(
    month: date | None = None,
    status_filter: PlanStatus | None = Query(default=None, alias="status"),
    assetClassId: int | None = None,
    assetId: int | None = None,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> list[TradePlan]:
    """Return planned trades of the current user with their month progress."""
    stmt = (
        select(TradePlanModel)
        .where(TradePlanModel.owner_id == user.id)
        .order_by(TradePlanModel.month, TradePlanModel.id)
    )
    if month is not None:
        stmt = stmt.where(TradePlanModel.month == month_start(month))
    if assetClassId is not None:
        stmt = stmt.where(TradePlanModel.asset_class_id == assetClassId)
    if assetId is not None:
        stmt = stmt.where(TradePlanModel.asset_id == assetId)
    plans = session.execute(stmt).scalars().all()

    totals = _load_totals(session, user.id)
    result = [to_api_plan(plan, totals) for plan in plans]
    if status_filter is not None:
        result = [plan for plan in result if plan.status == status_filter]
    return result


@router.post(
    "",
    response_model=TradePlan,
    status_code=status.HTTP_201_CREATED,
    summary="Plan a trade",
)
def create_trade_plan(
    payload: TradePlanCreate,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> TradePlan:
    """Plan a purchase or sale of a whole asset class or of one position."""
    asset_id, asset_class_id = _resolve_target(
        session, user.id, payload.assetId, payload.assetClassId
    )
    quantity = Decimal(str(payload.quantity)) if payload.quantity is not None else None
    amount = Decimal(str(payload.amount)) if payload.amount is not None else None
    _validate_target(asset_id, amount, quantity)

    plan = TradePlanModel(
        owner_id=user.id,
        asset_id=asset_id,
        asset_class_id=asset_class_id,
        month=month_start(payload.month),
        direction=payload.direction,
        amount=amount,
        quantity=quantity,
        note=payload.note,
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return to_api_plan(plan, _load_totals(session, user.id))


@router.patch("/{planId}", response_model=TradePlan, summary="Change a planned trade")
def update_trade_plan(
    planId: int,
    payload: TradePlanUpdate,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> TradePlan:
    """Update a planned trade; the target may be switched between class and asset."""
    plan = _get_owned_plan(session, user.id, planId)
    data = payload.model_dump(exclude_unset=True)

    if "assetId" in data or "assetClassId" in data:
        asset_id, asset_class_id = _resolve_target(
            session,
            user.id,
            data.get("assetId", plan.asset_id),
            data.get("assetClassId", plan.asset_class_id),
        )
        plan.asset_id = asset_id
        plan.asset_class_id = asset_class_id

    if "quantity" in data:
        plan.quantity = (
            Decimal(str(data["quantity"])) if data["quantity"] is not None else None
        )
        if plan.quantity is not None:
            plan.amount = None
    if data.get("amount") is not None:
        plan.amount = Decimal(str(data["amount"]))
        plan.quantity = None
    # Validate after applying both: switching between units and money must work
    # in a single request.
    _validate_target(plan.asset_id, plan.amount, plan.quantity)

    if data.get("month") is not None:
        plan.month = month_start(data["month"])
    if data.get("direction") is not None:
        plan.direction = data["direction"]
    if data.get("status") is not None:
        plan.status = data["status"]
    if "note" in data:
        plan.note = data["note"]

    session.commit()
    session.refresh(plan)
    return to_api_plan(plan, _load_totals(session, user.id))


@router.delete(
    "/{planId}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a planned trade"
)
def delete_trade_plan(
    planId: int,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> None:
    """Delete a planned trade."""
    plan = _get_owned_plan(session, user.id, planId)
    session.delete(plan)
    session.commit()
