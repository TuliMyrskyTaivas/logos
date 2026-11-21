from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import get_current_user, to_api_user
from ..models import User as UserModel
from ..schemas import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=User)
def read_current_user(user: UserModel = Depends(get_current_user)) -> User:
    """Return the authenticated user.

    The first request creates the very first user with the `admin` role.
    """
    return to_api_user(user)
