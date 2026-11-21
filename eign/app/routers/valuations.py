from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_frontend_db
from ..models import AssetClass as AssetClassModel
from ..models import User as UserModel
from ..models import Valuation as ValuationModel
from ..models import ValuationItem as ValuationItemModel
from ..schemas import Valuation, ValuationItem

router = APIRouter(prefix="/valuations", tags=["valuations"])


def _items_by_valuation(
    session: Session, valuation_ids: list[int]
) -> dict[int, list[ValuationItem]]:
    if not valuation_ids:
        return {}

    rows = session.execute(
        select(
            ValuationItemModel.valuation_id,
            AssetClassModel.id,
            AssetClassModel.code,
            ValuationItemModel.value,
        )
        .join(AssetClassModel, AssetClassModel.id == ValuationItemModel.asset_class_id)
        .where(ValuationItemModel.valuation_id.in_(valuation_ids))
        .order_by(ValuationItemModel.valuation_id, AssetClassModel.sort_order)
    ).all()

    grouped: dict[int, list[ValuationItem]] = {}
    for valuation_id, class_id, class_code, value in rows:
        grouped.setdefault(valuation_id, []).append(
            ValuationItem(
                assetClassId=class_id,
                assetClassCode=class_code,
                value=float(value),
            )
        )
    return grouped


def _to_api(snapshot: ValuationModel, items: list[ValuationItem]) -> Valuation:
    return Valuation(
        id=snapshot.id,
        valuationDate=snapshot.valuation_date,
        totalValue=float(snapshot.total_value),
        currency=snapshot.currency,
        items=items,
        createdAt=snapshot.created_at,
    )


@router.get("", response_model=list[Valuation], summary="List stored valuations")
def list_valuations(
    dateFrom: date | None = None,
    dateTo: date | None = None,
    limit: int = Query(default=24, ge=1, le=240),
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> list[Valuation]:
    """Return the current user's snapshots, newest first."""
    stmt = (
        select(ValuationModel)
        .where(ValuationModel.owner_id == user.id)
        .order_by(ValuationModel.valuation_date.desc())
        .limit(limit)
    )
    if dateFrom is not None:
        stmt = stmt.where(ValuationModel.valuation_date >= dateFrom)
    if dateTo is not None:
        stmt = stmt.where(ValuationModel.valuation_date <= dateTo)

    snapshots = session.execute(stmt).scalars().all()
    items = _items_by_valuation(session, [snapshot.id for snapshot in snapshots])
    return [_to_api(snapshot, items.get(snapshot.id, [])) for snapshot in snapshots]


@router.get("/latest", response_model=Valuation, summary="Get the latest valuation")
def get_latest_valuation(
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> Valuation:
    """Return the most recent stored snapshot of the current user."""
    snapshot = session.execute(
        select(ValuationModel)
        .where(ValuationModel.owner_id == user.id)
        .order_by(ValuationModel.valuation_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valuations stored yet",
        )

    items = _items_by_valuation(session, [snapshot.id])
    return _to_api(snapshot, items.get(snapshot.id, []))
