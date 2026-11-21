from __future__ import annotations

from decimal import Decimal
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import get_frontend_db
from ..models import Asset as AssetModel
from ..models import AssetClass as AssetClassModel
from ..models import Trade as TradeModel
from ..models import User as UserModel
from ..schemas import Asset, AssetCreate, AssetUnit, AssetUpdate

router = APIRouter(prefix="/assets", tags=["assets"])

METAL_CLASS_CODE = "METAL"


def to_api_asset(asset: AssetModel) -> Asset:
    """Convert the ORM position into the API representation."""
    return Asset(
        id=asset.id,
        assetClassId=asset.asset_class_id,
        assetClassCode=asset.asset_class.code,
        name=asset.name,
        ticker=asset.ticker,
        isin=asset.isin,
        metalCode=asset.metal_code,
        currency=asset.currency,
        quantity=float(asset.quantity),
        unit=cast(AssetUnit, asset.unit),
        avgPurchasePrice=(
            float(asset.avg_purchase_price) if asset.avg_purchase_price is not None else None
        ),
        currentPrice=float(asset.current_price) if asset.current_price is not None else None,
        custodian=asset.custodian,
        createdAt=asset.created_at,
        updatedAt=asset.updated_at,
    )


def get_owned_asset(session: Session, owner_id: int, asset_id: int) -> AssetModel:
    """Return the position of the current user or raise 404."""
    asset = session.execute(
        select(AssetModel)
        .options(joinedload(AssetModel.asset_class))
        .where(AssetModel.id == asset_id, AssetModel.owner_id == owner_id)
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    return asset


def _get_asset_class(session: Session, asset_class_id: int) -> AssetClassModel:
    asset_class = session.get(AssetClassModel, asset_class_id)
    if asset_class is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset class {asset_class_id} does not exist",
        )
    return asset_class


def _validate_metal_code(asset_class: AssetClassModel, metal_code: str | None) -> None:
    """Metals must carry a metal code, all other classes must not."""
    if asset_class.code == METAL_CLASS_CODE and not metal_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="metal_code is required for the METAL asset class",
        )
    if asset_class.code != METAL_CLASS_CODE and metal_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="metal_code is only allowed for the METAL asset class",
        )


def _has_trades(session: Session, asset_id: int) -> bool:
    return (
        session.execute(select(TradeModel.id).where(TradeModel.asset_id == asset_id).limit(1)).first()
        is not None
    )


def _ensure_unique_name(
    session: Session,
    owner_id: int,
    name: str,
    exclude_asset_id: int | None = None,
) -> None:
    stmt = select(AssetModel.id).where(
        AssetModel.owner_id == owner_id, AssetModel.name == name
    )
    if exclude_asset_id is not None:
        stmt = stmt.where(AssetModel.id != exclude_asset_id)
    if session.execute(stmt).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset '{name}' already exists",
        )


@router.get("", response_model=list[Asset], summary="List positions")
def list_assets(
    assetClassId: int | None = None,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> list[Asset]:
    """Return the current user's positions, optionally filtered by class."""
    stmt = (
        select(AssetModel)
        .options(joinedload(AssetModel.asset_class))
        .where(AssetModel.owner_id == user.id)
        .order_by(AssetModel.id)
    )
    if assetClassId is not None:
        stmt = stmt.where(AssetModel.asset_class_id == assetClassId)
    assets = session.execute(stmt).scalars().all()
    return [to_api_asset(asset) for asset in assets]


@router.get("/{assetId}", response_model=Asset, summary="Get a position")
def get_asset(
    assetId: int,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> Asset:
    """Return one of the current user's positions."""
    return to_api_asset(get_owned_asset(session, user.id, assetId))


@router.post("", response_model=Asset, status_code=status.HTTP_201_CREATED, summary="Create a position")
def create_asset(
    payload: AssetCreate,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> Asset:
    """Create a position. Its quantity may be set manually while it has no trades."""
    asset_class = _get_asset_class(session, payload.assetClassId)
    _validate_metal_code(asset_class, payload.metalCode)
    _ensure_unique_name(session, user.id, payload.name)

    asset = AssetModel(
        owner_id=user.id,
        asset_class=asset_class,
        name=payload.name,
        ticker=payload.ticker,
        isin=payload.isin,
        metal_code=payload.metalCode,
        currency=payload.currency,
        quantity=Decimal(str(payload.quantity)),
        unit=payload.unit,
        avg_purchase_price=(
            Decimal(str(payload.avgPurchasePrice))
            if payload.avgPurchasePrice is not None
            else None
        ),
        current_price=(
            Decimal(str(payload.currentPrice)) if payload.currentPrice is not None else None
        ),
        custodian=payload.custodian,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return to_api_asset(asset)


@router.patch("/{assetId}", response_model=Asset, summary="Update a position")
def update_asset(
    assetId: int,
    payload: AssetUpdate,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> Asset:
    """Update a position.

    Quantity and average purchase price are derived from trades, so they can
    only be changed while the position has no trades.
    """
    asset = get_owned_asset(session, user.id, assetId)
    data = payload.model_dump(exclude_unset=True)

    derived_fields = {"quantity", "avgPurchasePrice"} & data.keys()
    if derived_fields and _has_trades(session, asset.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Quantity and average purchase price are derived from trades",
        )

    # Required fields: an explicit null is ignored, like an omitted field.
    if data.get("name") is not None:
        _ensure_unique_name(session, user.id, data["name"], exclude_asset_id=asset.id)
        asset.name = data["name"]

    asset_class = asset.asset_class
    if data.get("assetClassId") is not None:
        asset_class = _get_asset_class(session, data["assetClassId"])
        asset.asset_class = asset_class

    if "metalCode" in data or data.get("assetClassId") is not None:
        metal_code = data.get("metalCode", asset.metal_code)
        _validate_metal_code(asset_class, metal_code)
        asset.metal_code = metal_code

    if data.get("unit") is not None:
        asset.unit = data["unit"]
    if data.get("currency") is not None:
        asset.currency = data["currency"]
    if data.get("quantity") is not None:
        asset.quantity = Decimal(str(data["quantity"]))

    # Nullable fields: an explicit null clears the value.
    if "ticker" in data:
        asset.ticker = data["ticker"]
    if "isin" in data:
        asset.isin = data["isin"]
    if "custodian" in data:
        asset.custodian = data["custodian"]
    if "avgPurchasePrice" in data:
        value = data["avgPurchasePrice"]
        asset.avg_purchase_price = Decimal(str(value)) if value is not None else None
    if "currentPrice" in data:
        value = data["currentPrice"]
        asset.current_price = Decimal(str(value)) if value is not None else None

    session.commit()
    session.refresh(asset)
    return to_api_asset(asset)


@router.delete("/{assetId}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a position")
def delete_asset(
    assetId: int,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> None:
    """Delete a position together with its trade history (database cascade)."""
    asset = get_owned_asset(session, user.id, assetId)
    session.delete(asset)
    session.commit()
