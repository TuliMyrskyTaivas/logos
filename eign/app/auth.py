from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .database import get_frontend_db
from .models import User as UserModel
from .schemas import User, UserRole

# Identity headers set by nginx after it verified the client certificate.
CLIENT_VERIFY_HEADER = "X-SSL-Client-Verify"
CLIENT_CN_HEADER = "X-Client-CN"

# `last_login_at` is refreshed at most once a day to avoid a write per request.
LOGIN_TOUCH_INTERVAL = timedelta(days=1)

# Arbitrary constant key for the transaction-scoped advisory lock that makes
# first-user provisioning safe under concurrent requests.
_PROVISION_LOCK_KEY = 731_0001


def to_api_user(user: UserModel) -> User:
    """Convert the ORM user into the API representation."""
    return User(
        id=user.id,
        login=user.login,
        role=cast(UserRole, user.role),
        isActive=user.is_active,
        baseCurrency=user.base_currency,
        lastLoginAt=user.last_login_at,
    )


def get_client_login(request: Request) -> str:
    """Return the login forwarded by nginx for a verified client certificate."""
    verify = request.headers.get(CLIENT_VERIFY_HEADER, "").strip().upper()
    login = request.headers.get(CLIENT_CN_HEADER, "").strip()
    if verify != "SUCCESS" or not login:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A verified client certificate is required",
        )
    return login


def _provision_first_user(login: str, session: Session) -> UserModel | None:
    """Create the very first user as an administrator.

    Returns None when users already exist, i.e. provisioning is not allowed.
    """
    # Serialise concurrent first requests so only one user can be created.
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _PROVISION_LOCK_KEY})
    if session.execute(select(UserModel.id).limit(1)).first() is not None:
        session.rollback()
        return None

    user = UserModel(login=login, role="admin")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _touch_last_login(user: UserModel, session: Session) -> None:
    now = datetime.now(UTC)
    if user.last_login_at is not None and now - user.last_login_at < LOGIN_TOUCH_INTERVAL:
        return
    user.last_login_at = now
    session.commit()


def get_current_user(
    request: Request,
    session: Session = Depends(get_frontend_db),
) -> UserModel:
    """Authenticate the caller from nginx headers and load the local user row."""
    login = get_client_login(request)
    user = session.execute(
        select(UserModel).where(UserModel.login == login)
    ).scalar_one_or_none()

    if user is None:
        user = _provision_first_user(login, session)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not registered; ask an administrator to create it",
            )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is deactivated",
        )

    _touch_last_login(user, session)
    return user


def require_admin(user: UserModel = Depends(get_current_user)) -> UserModel:
    """Dependency guarding administrator-only endpoints."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges are required",
        )
    return user
