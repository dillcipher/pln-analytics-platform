from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.application.dto.auth_dto import (
    CurrentUserResponse,
    LoginResponse,
)
from app.core.config import get_settings
from app.core.security import create_access_token
from app.infrastructure.auth.user_store import (
    AuthenticatedUser,
    UserStore,
)
from app.interface.api.deps import (
    get_current_user,
    get_user_store,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_store: UserStore = Depends(get_user_store),
) -> LoginResponse:

    logger.info("========================================")
    logger.info("LOGIN REQUEST")
    logger.info("Username : %r", form_data.username)
    logger.info("Password Length : %s", len(form_data.password))

    user = user_store.authenticate(
        form_data.username,
        form_data.password,
    )

    logger.info("Authenticate Result : %s", user)

    if user is None:

        logger.warning(
            "Login failed for username=%s",
            form_data.username,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    settings = get_settings()

    token = create_access_token(
        subject=user.username,
        secret_key=settings.JWT_SECRET_KEY,
        expires_minutes=settings.JWT_EXPIRES_MINUTES,
        extra_claims={
            "role": user.role,
        },
    )

    logger.info(
        "Login success for user=%s role=%s",
        user.username,
        user.role,
    )

    logger.info("========================================")

    return LoginResponse(
        access_token=token,
        expires_in_minutes=settings.JWT_EXPIRES_MINUTES,
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def me(
    user: AuthenticatedUser = Depends(get_current_user),
) -> CurrentUserResponse:

    return CurrentUserResponse(
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        unitupi_scope=user.unitupi_scope,
    )