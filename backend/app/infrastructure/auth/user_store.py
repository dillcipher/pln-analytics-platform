"""
User Store
==========
Lightweight, file-backed user credential store for an internal tool
with a small, centrally-managed user list (no self-service signup).
Deliberately NOT a full RDBMS-backed user table — that would mean
running/paying for a database server for a handful of rows. If PLN
later wants self-service accounts, SSO, or per-request role changes,
swap this class for a real repository without touching any caller (it's
accessed only through the `UserStore` interface below).

File format (`data/auth/users.json`):
    {
      "<username>": {
        "username": "...",
        "full_name": "...",
        "password_hash": "pbkdf2_sha256$...",
        "role": "admin" | "analyst" | "viewer",
        "unitupi_scope": null | "UID LAMPUNG"   # null = full access
      }, ...
    }
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.security import verify_password

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthenticatedUser:
    username: str
    full_name: str
    role: str
    unitupi_scope: str | None


class UserStore:
    def __init__(self, users_file: Path):
        self._users_file = users_file
        self._users: dict[str, dict] = {}
        self.reload()

    def reload(self) -> None:
        if not self._users_file.exists():
            logger.error("Users file not found at %s — no one will be able to log in", self._users_file)
            self._users = {}
            return
        with self._users_file.open(encoding="utf-8") as fh:
            self._users = json.load(fh)
        logger.info("Loaded %d user(s) from %s", len(self._users), self._users_file)

    def authenticate(self, username: str, password: str) -> AuthenticatedUser | None:
        record = self._users.get(username)
        if record is None:
            return None
        if not verify_password(password, record["password_hash"]):
            return None
        return AuthenticatedUser(
            username=record["username"],
            full_name=record["full_name"],
            role=record["role"],
            unitupi_scope=record.get("unitupi_scope"),
        )

    def get(self, username: str) -> AuthenticatedUser | None:
        record = self._users.get(username)
        if record is None:
            return None
        return AuthenticatedUser(
            username=record["username"],
            full_name=record["full_name"],
            role=record["role"],
            unitupi_scope=record.get("unitupi_scope"),
        )
