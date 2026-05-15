"""JWT creation/verification and refresh-token hashing utilities.

- Access tokens: short-lived (15 min by default), HS256, returned in JSON body.
- Refresh tokens: opaque random strings; only their bcrypt hash is stored in DB.
  The raw token is set as an httpOnly Secure SameSite=Lax cookie. Never logged.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict
from uuid import UUID

import bcrypt
import jwt

from app.core.config import get_settings


class TokenPayload(TypedDict):
    sub: str          # user UUID
    email: str
    role: str
    exp: int
    iat: int
    type: str         # "access"


# ── Access tokens ───────────────────────────────────────────────

def create_access_token(*, user_id: UUID, email: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_access_token_minutes)).timestamp()),
        "type": "access",
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> TokenPayload:
    settings = get_settings()
    decoded: dict[str, Any] = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )
    if decoded.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return decoded  # type: ignore[return-value]


# ── Refresh tokens ──────────────────────────────────────────────

def generate_refresh_token() -> str:
    """Cryptographically random 256-bit opaque token, URL-safe base64."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return bcrypt.hashpw(token.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_refresh_token(token: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(token.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def refresh_token_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_days)
