"""
Shared FastAPI dependencies.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import get_settings
from app.core.security import (
    TokenError,
    decode_access_token,
)
from app.infrastructure.auth.user_store import (
    AuthenticatedUser,
    UserStore,
)
from app.infrastructure.duckdb.dlpd_repository import (
    DuckDbDlpdRepository,
)
from app.infrastructure.duckdb.executive_repository import (
    DuckDbExecutiveRepository,
)
from app.infrastructure.duckdb.suspect_repository import (
    DuckDbSuspectRepository,
)

_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


@lru_cache
def get_user_store() -> UserStore:
    settings = get_settings()
    return UserStore(settings.USERS_FILE)


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _developer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        username="developer",
        full_name="Developer",
        role="admin",
        unitupi_scope=None,
    )


def get_current_user(
    token: str | None = Depends(_oauth2_scheme),
) -> AuthenticatedUser:
    settings = get_settings()

    # The deployed frontend currently has no login/token flow. Authentication
    # is therefore opt-in through AUTH_REQUIRED=true. DEBUG remains a separate
    # developer setting and is not used as a production auth switch.
    if not settings.AUTH_REQUIRED:
        return _developer_user()

    if settings.DEBUG:
        return _developer_user()

    if not token:
        raise _unauthorized()

    try:
        payload = decode_access_token(
            token,
            settings.JWT_SECRET_KEY,
        )
    except (TokenError, TypeError, ValueError, AttributeError) as exc:
        raise _unauthorized("Invalid or expired credentials") from exc

    user = get_user_store().get(
        payload.get("sub", ""),
    )

    if user is None:
        raise _unauthorized("User no longer exists")

    return user


def require_admin(
    user: AuthenticatedUser = Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return user


@lru_cache
def get_dlpd_repository() -> DuckDbDlpdRepository:
    return DuckDbDlpdRepository()


@lru_cache
def get_executive_repository() -> DuckDbExecutiveRepository:
    return DuckDbExecutiveRepository()


@lru_cache
def get_suspect_repository() -> DuckDbSuspectRepository:
    return DuckDbSuspectRepository()
