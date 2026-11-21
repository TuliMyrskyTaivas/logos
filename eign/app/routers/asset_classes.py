from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_frontend_db
from ..models import AssetClass as AssetClassModel
from ..models import User as UserModel
from ..schemas import AssetClassInfo

router = APIRouter(prefix="/asset-classes", tags=["asset-classes"])


@router.get("", response_model=list[AssetClassInfo], summary="List asset classes")
def list_asset_classes(
    _user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> list[AssetClassInfo]:
    """Return the asset class dictionary used by positions and plans."""
    classes = session.execute(
        select(AssetClassModel).order_by(AssetClassModel.sort_order, AssetClassModel.id)
    ).scalars().all()
    return [
        AssetClassInfo(
            id=asset_class.id,
            code=asset_class.code,
            name=asset_class.name,
            sortOrder=asset_class.sort_order,
        )
        for asset_class in classes
    ]
