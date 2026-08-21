from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from app.core.constants import PROCESSED, RAW, RAW_UPLOAD

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _env_list(name: str, defaults: list[str]) -> list[str]:
    """Read a comma-separated list while always preserving required origins."""
    value = os.getenv(name)
    configured = (
        [item.strip().rstrip("/") for item in value.split(",") if item.strip()]
        if value and value.strip()
        else []
    )

    result: list[str] = []
    for item in [*defaults, *configured]:
        normalized = item.strip().rstrip("/")
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value.strip()) if value and value.strip() else default


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "PLN Analytics Platform API")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    DEBUG: bool = _env_bool("DEBUG", False)

    # The deployed frontend currently has no login screen/token flow.
    # Authentication therefore remains OFF unless it is deliberately enabled
    # with BOTH flags. The second gate prevents a stale AUTH_REQUIRED=true
    # environment variable from breaking the public dashboard with 401/500s.
    # When a real login flow is ready, set:
    #   AUTH_ENABLED=true
    #   AUTH_REQUIRED=true
    AUTH_REQUIRED: bool = (
        _env_bool("AUTH_ENABLED", False)
        and _env_bool("AUTH_REQUIRED", False)
    )

    CORS_ORIGINS: list[str] = _env_list(
        "CORS_ORIGINS",
        [
            "https://pln-analytics.vercel.app",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
    )

    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY",
        "CHANGE-ME-IN-PRODUCTION-this-is-not-secure",
    )
    JWT_EXPIRES_MINUTES: int = _env_int("JWT_EXPIRES_MINUTES", 480)

    USERS_FILE: Path = _env_path(
        "USERS_FILE",
        BACKEND_ROOT / "data" / "auth" / "users.json",
    )

    # IMPORTANT: ETL, DuckDB and processed-artifact persistence all use the
    # canonical paths from app.core.constants. Keeping Settings on the same
    # paths prevents misleading startup diagnostics and split local storage
    # between /app/data and /app/backend/data.
    DATA_PROCESSED_DIR: Path = _env_path(
        "DATA_PROCESSED_DIR",
        PROCESSED,
    )
    DATA_RAW_DIR: Path = _env_path(
        "DATA_RAW_DIR",
        RAW,
    )
    DATA_INCOMING_DIR: Path = _env_path(
        "DATA_INCOMING_DIR",
        RAW_UPLOAD,
    )
    DATA_AUTH_DIR: Path = _env_path(
        "DATA_AUTH_DIR",
        BACKEND_ROOT / "data" / "auth",
    )

    DEFAULT_PAGE_SIZE: int = _env_int("DEFAULT_PAGE_SIZE", 50)
    MAX_PAGE_SIZE: int = _env_int("MAX_PAGE_SIZE", 500)
    CACHE_TTL_SECONDS: int = _env_int("CACHE_TTL_SECONDS", 120)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
