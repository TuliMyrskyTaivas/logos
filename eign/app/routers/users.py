from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_admin, to_api_user
from ..database import get_frontend_db
from ..models import User as UserModel
from ..schemas import User, UserCreate, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def _get_user(session: Session, user_id: int) -> UserModel:
    user = session.get(UserModel, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


def _active_admin_count(session: Session) -> int:
    return (
        session.execute(
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.role == "admin", UserModel.is_active.is_(True))
        ).scalar_one()
    )


def _ensure_admin_remains(session: Session, user: UserModel) -> None:
    """Refuse changes that would leave the service without an active admin."""
    if user.role == "admin" and user.is_active and _active_admin_count(session) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove the last active administrator",
        )


@router.get("", response_model=list[User], summary="List users")
def list_users(
    _admin: UserModel = Depends(require_admin),
    session: Session = Depends(get_frontend_db),
) -> list[User]:
    """Return all users, including deactivated ones."""
    users = session.execute(select(UserModel).order_by(UserModel.id)).scalars().all()
    return [to_api_user(user) for user in users]


@router.post(
    "",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
)
def create_user(
    payload: UserCreate,
    _admin: UserModel = Depends(require_admin),
    session: Session = Depends(get_frontend_db),
) -> User:
    """Register a new user. Certificates are issued by an external CA."""
    exists = session.execute(
        select(UserModel.id).where(UserModel.login == payload.login)
    ).first()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{payload.login}' already exists",
        )

    user = UserModel(login=payload.login, role=payload.role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return to_api_user(user)


@router.patch("/{userId}", response_model=User, summary="Update a user")
def update_user(
    userId: int,
    payload: UserUpdate,
    admin: UserModel = Depends(require_admin),
    session: Session = Depends(get_frontend_db),
) -> User:
    """Change the role or the activation status of a user.

    Administrators may edit their own record, but the service always keeps at
    least one active administrator.
    """
    user = _get_user(session, userId)
    data = payload.model_dump(exclude_unset=True)

    new_role = data.get("role", user.role)
    new_active = data.get("isActive", user.is_active)
    if user.role == "admin" and user.is_active and (new_role != "admin" or not new_active):
        _ensure_admin_remains(session, user)

    if "role" in data:
        user.role = data["role"]
    if "isActive" in data:
        user.is_active = data["isActive"]

    session.commit()
    session.refresh(user)
    return to_api_user(user)


@router.delete(
    "/{userId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a user",
)
def delete_user(
    userId: int,
    admin: UserModel = Depends(require_admin),
    session: Session = Depends(get_frontend_db),
) -> None:
    """Soft-delete a user: portfolio history is kept, sign-in is blocked."""
    if userId == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrators cannot deactivate themselves",
        )

    user = _get_user(session, userId)
    user.is_active = False
    session.commit()
