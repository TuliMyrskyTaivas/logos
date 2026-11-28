from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user, to_api_user
from ..database import get_frontend_db
from ..models import User as UserModel
from ..schemas import User, UserSettingsUpdate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=User)
def read_current_user(user: UserModel = Depends(get_current_user)) -> User:
    """Return the authenticated user.

    The first request creates the very first user with the `admin` role.
    """
    return to_api_user(user)


@router.patch("/me", response_model=User, summary="Update own settings")
def update_own_settings(
    payload: UserSettingsUpdate,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_frontend_db),
) -> User:
    """Change the caller's base currency and risk-free rate.

    Both fields are optional; an explicit `null` risk-free rate restores the
    service-wide default.
    """
    data = payload.model_dump(exclude_unset=True)

    if data.get("baseCurrency") is not None:
        user.base_currency = data["baseCurrency"].strip().upper()
    if "riskFreeRate" in data:
        user.risk_free_rate = (
            Decimal(str(data["riskFreeRate"]))
            if data["riskFreeRate"] is not None
            else None
        )

    session.commit()
    session.refresh(user)
    return to_api_user(user)
