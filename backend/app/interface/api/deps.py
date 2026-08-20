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

    return UserStore(
        settings.USERS_FILE,
    )


def get_current_user(
    token: str | None = Depends(_oauth2_scheme),
) -> AuthenticatedUser:

    settings = get_settings()

    # ==========================================================
    # DEVELOPMENT
    # ==========================================================

    if settings.DEBUG:
    
        return AuthenticatedUser(
        username="developer",
        full_name="Developer",
        role="admin",
        unitupi_scope=None,
    )

    # ==========================================================
    # PRODUCTION
    # ==========================================================

    try:

        payload = decode_access_token(
            token,
            settings.JWT_SECRET_KEY,
        )

    except TokenError as exc:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired credentials",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    user = get_user_store().get(
        payload.get(
            "sub",
            "",
        ),
    )

    if user is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    return user


def require_admin(
    user: AuthenticatedUser = Depends(
        get_current_user,
    ),
) -> AuthenticatedUser:

    if user.role != "admin":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    return user


# ==========================================================
# Repository Providers
# ==========================================================

@lru_cache
def get_executive_repository() -> DuckDbExecutiveRepository:

    return DuckDbExecutiveRepository()


@lru_cache
def get_dlpd_repository() -> DuckDbDlpdRepository:

    return DuckDbDlpdRepository()


@lru_cache
def get_suspect_repository() -> DuckDbSuspectRepository:

    return DuckDbSuspectRepository()