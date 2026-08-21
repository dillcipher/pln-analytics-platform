from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(
    subject: str,
    secret_key: str,
    expires_minutes: int,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_minutes * 60,
    }
    if extra_claims:
        payload.update(extra_claims)

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


class TokenError(Exception):
    """Raised for invalid, tampered, missing, or expired tokens."""


def decode_access_token(token: str | None, secret_key: str) -> dict[str, Any]:
    """Decode and verify a JWT without leaking parser errors as HTTP 500."""
    if not token or not isinstance(token, str):
        raise TokenError("Missing access token")

    parts = token.split(".")
    if len(parts) != 3 or any(not part for part in parts):
        raise TokenError("Malformed token")

    header_b64, payload_b64, signature_b64 = parts
    try:
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_signature = hmac.new(
            secret_key.encode("utf-8"), signing_input, hashlib.sha256
        ).digest()
        actual_signature = _b64url_decode(signature_b64)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise TokenError("Malformed token signature") from exc

    if not hmac.compare_digest(expected_signature, actual_signature):
        raise TokenError("Signature verification failed")

    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise TokenError("Malformed token payload") from exc

    if not isinstance(payload, dict):
        raise TokenError("Invalid token payload")

    if "exp" in payload:
        try:
            if int(time.time()) > int(payload["exp"]):
                raise TokenError("Token expired")
        except (TypeError, ValueError) as exc:
            raise TokenError("Invalid token expiry") from exc

    return payload


def hash_password(password: str) -> str:
    """Create a PBKDF2-SHA256 password hash compatible with UserStore."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must not be empty")
    iterations = 310_000
    salt = _b64url_encode(__import__("secrets").token_bytes(16))
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), iterations
    )
    return f"pbkdf2_sha256${iterations}${salt}${_b64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a PBKDF2-SHA256 hash stored as pbkdf2_sha256$iterations$salt$digest."""
    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False

    try:
        scheme, iterations_raw, salt, expected = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        if iterations <= 0 or not salt or not expected:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("ascii"), iterations
        )
        return hmac.compare_digest(_b64url_encode(actual), expected)
    except (ValueError, TypeError, UnicodeError):
        return False
