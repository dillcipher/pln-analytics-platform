"""
Centralized, environment-driven configuration.

Nothing sensitive is hardcoded.
Everything can be overridden through environment variables.

The same configuration is intended to work for:

    - Local development
    - Render
    - CI / deployment environments
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


# ==========================================================
# PROJECT ROOT
# ==========================================================

BACKEND_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


# ==========================================================
# ENVIRONMENT HELPERS
# ==========================================================


def _env_bool(
    name: str,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _env_int(
    name: str,
    default: int,
) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    value = value.strip()

    if not value:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _env_list(
    name: str,
    defaults: list[str],
) -> list[str]:
    value = os.getenv(name)

    if value is None:
        return defaults.copy()

    value = value.strip()

    if not value:
        return defaults.copy()

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def _env_path(
    name: str,
    default: Path,
) -> Path:
    value = os.getenv(name)

    if value is None:
        return default

    value = value.strip()

    if not value:
        return default

    return Path(value)


# ==========================================================
# SETTINGS
# ==========================================================


class Settings:

    # ======================================================
    # APP
    # ======================================================

    APP_NAME: str = os.getenv(
        "APP_NAME",
        "PLN Analytics Platform API",
    )

    ENVIRONMENT: str = os.getenv(
        "ENVIRONMENT",
        "development",
    )

    DEBUG: bool = _env_bool(
        "DEBUG",
        True,
    )

    # ======================================================
    # CORS
    # ======================================================

    CORS_ORIGINS: list[str] = _env_list(
        "CORS_ORIGINS",
        [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
    )

    # ======================================================
    # AUTH
    # ======================================================

    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY",
        "CHANGE-ME-IN-PRODUCTION-this-is-not-secure",
    )

    JWT_EXPIRES_MINUTES: int = _env_int(
        "JWT_EXPIRES_MINUTES",
        480,
    )

    USERS_FILE: Path = _env_path(
        "USERS_FILE",
        BACKEND_ROOT
        / "data"
        / "auth"
        / "users.json",
    )

    # ======================================================
    # DATA
    # ======================================================
    #
    # IMPORTANT:
    #
    # The current project structure is:
    #
    # backend/
    #   data/
    #     processed/
    #
    # Therefore the default path MUST be:
    #
    #   BACKEND_ROOT / data / processed
    #
    # The environment variable can override this when
    # deploying to a persistent disk.
    #
    # Example Render:
    #
    #   DATA_PROCESSED_DIR=/var/data/processed
    #
    # ======================================================

    DATA_PROCESSED_DIR: Path = _env_path(
        "DATA_PROCESSED_DIR",
        BACKEND_ROOT
        / "data"
        / "processed",
    )

    # ======================================================
    # RAW DATA
    # ======================================================
    #
    # Raw files are kept separate from processed data.
    #
    # Dashboard APIs should NOT read raw Excel directly.
    #
    # ======================================================

    DATA_RAW_DIR: Path = _env_path(
        "DATA_RAW_DIR",
        BACKEND_ROOT
        / "data"
        / "raw",
    )

    DATA_INCOMING_DIR: Path = _env_path(
        "DATA_INCOMING_DIR",
        BACKEND_ROOT
        / "data"
        / "raw"
        / "incoming",
    )

    # ======================================================
    # AUTH DATA
    # ======================================================

    DATA_AUTH_DIR: Path = _env_path(
        "DATA_AUTH_DIR",
        BACKEND_ROOT
        / "data"
        / "auth",
    )

    # ======================================================
    # PAGINATION / PERFORMANCE
    # ======================================================

    DEFAULT_PAGE_SIZE: int = _env_int(
        "DEFAULT_PAGE_SIZE",
        50,
    )

    MAX_PAGE_SIZE: int = _env_int(
        "MAX_PAGE_SIZE",
        500,
    )

    CACHE_TTL_SECONDS: int = _env_int(
        "CACHE_TTL_SECONDS",
        120,
    )


# ==========================================================
# SETTINGS SINGLETON
# ==========================================================


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()