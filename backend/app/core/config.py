from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

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

    # The production Vercel frontend is mandatory. Environment variables may
    # add extra origins, but must never accidentally remove the production UI.
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

    DATA_PROCESSED_DIR: Path = _env_path(
        "DATA_PROCESSED_DIR",
        BACKEND_ROOT / "data" / "processed",
    )
    DATA_RAW_DIR: Path = _env_path(
        "DATA_RAW_DIR",
        BACKEND_ROOT / "data" / "raw",
    )
    DATA_INCOMING_DIR: Path = _env_path(
        "DATA_INCOMING_DIR",
        BACKEND_ROOT / "data" / "raw" / "incoming",
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
