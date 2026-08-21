"""
Security primitives: password hashing and JWT issuing/verification.

Deliberately implemented with the Python standard library only
(`hashlib`, `hmac`, `secrets`, `base64`, `json`) instead of
python-jose/passlib/bcrypt. For an internal enterprise tool this removes
two dependencies (and their C-extension build requirements, which are a
common source of deployment friction on constrained free-tier hosts)
while still using algorithms considered secure for this purpose:

    - Passwords: PBKDF2-HMAC-SHA256, 260,000 iterations, random 16-byte
      salt per password (NIST SP 800-132 compliant parameters).
    - Tokens: JWT with HS256 (HMAC-SHA256), using a server-side secret
      key. This is the same algorithm python-jose would use here; we're
      just not pulling in the whole library for one algorithm.

If/when the platform grows into needing RS256 (asymmetric, for
multi-service token verification) or social/SSO login, swap this module
out — every caller only depends on the four functions below, not on the
implementation.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

PBKDF2_ITERATIONS = 260_000
SALT_BYTES = 16


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Returns 'pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>'."""
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_hex, hash_hex = stored_hash.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False

    iterations = int(iterations_str)
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(hash_hex)
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(candidate, expected)


# --------------------------------------------------------------------------
# JWT (HS256) — minimal, dependency-free implementation
# --------------------------------------------------------------------------

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

    header_b64 = _b64url_encode(
        json.dumps(header, separators=(",", ":")).encode()
    )
    payload_b64 = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode()
    )
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    signature_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


class TokenError(Exception):
    """Raised for any invalid, tampered, or expired token."""


def decode_access_token(
    token: str | None,
    secret_key: str,
) -> dict[str, Any]:
    """Decode and verify a JWT.

    ``None``/empty input is treated as an authentication failure rather than
    leaking an AttributeError from ``str.split`` into FastAPI as HTTP 500.
    """
    if not token or not isinstance(token, str):
        raise TokenError("Missing access token")

    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except (ValueError, AttributeError) as exc:
        raise TokenError("Malformed token") from exc

    if not header_b64 or not payload_b64 or not signature_b64:
        raise TokenError("Malformed token")

    try:
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_signature = hmac.new(
            secret_key.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        actual_signature = _b64url_decode(signature_b64)
    except (ValueError, TypeError) as exc:
        raise TokenError("Malformed token") from exc

    if not hmac.compare_digest(expected_signature, actual_signature):
        raise TokenError("Signature verification failed")

    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
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
