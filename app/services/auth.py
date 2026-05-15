"""Google OAuth 2.0 SSO + JWT issuance.

Flow:
  1. Frontend hits /api/v1/auth/google/login → 307 to Google's authorize URL
     with a signed state token (itsdangerous, 10-min TTL).
  2. Google redirects back to /api/v1/auth/google/callback with code + state.
  3. We verify state, exchange code for tokens, fetch userinfo, upsert User,
     issue our own JWT access + refresh, set httpOnly cookies, and 307 the
     browser to FRONTEND_BASE_URL.

OAuth client_id / client_secret come from the DB settings table first (so the
Admin Portal can rotate them in Phase C) and fall back to env vars.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.services import settings_store

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
STATE_SALT = "ts-oauth-state"
STATE_TTL_SECONDS = 600


class OAuthError(Exception):
    """Raised when the OAuth flow fails for any reason worth surfacing as 4xx."""


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True)
class GoogleUserInfo:
    sub: str
    email: str
    name: str
    picture: str | None


# ── Config resolution ──────────────────────────────────────────────────────

async def get_oauth_config(db: AsyncSession) -> GoogleOAuthConfig:
    env = get_settings()
    client_id = await settings_store.get_setting(
        db, "google_oauth_client_id", default=env.google_oauth_client_id
    )
    client_secret = await settings_store.get_setting(
        db,
        "google_oauth_client_secret",
        default=env.google_oauth_client_secret.get_secret_value(),
    )
    if not client_id or not client_secret:
        raise OAuthError(
            "Google OAuth is not configured. Set GOOGLE_OAUTH_CLIENT_ID and "
            "GOOGLE_OAUTH_CLIENT_SECRET in .env, or configure them via the Admin Portal."
        )
    return GoogleOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=env.google_oauth_redirect_uri,
    )


# ── State (CSRF) ───────────────────────────────────────────────────────────

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        get_settings().app_secret_key.get_secret_value(), salt=STATE_SALT
    )


def make_state() -> str:
    nonce = secrets.token_urlsafe(16)
    return _serializer().dumps(nonce)


def verify_state(token: str) -> None:
    try:
        _serializer().loads(token, max_age=STATE_TTL_SECONDS)
    except BadSignature as exc:
        raise OAuthError("Invalid or expired OAuth state") from exc


# ── Authorize URL ──────────────────────────────────────────────────────────

def build_authorize_url(cfg: GoogleOAuthConfig, state: str) -> str:
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": state,
    }
    return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"


# ── Callback: exchange code, fetch userinfo ────────────────────────────────

async def exchange_code(cfg: GoogleOAuthConfig, code: str) -> str:
    """Returns the Google access_token. We don't persist Google's tokens —
    we just need them once to fetch the user's profile."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": cfg.client_id,
                "client_secret": cfg.client_secret,
                "redirect_uri": cfg.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise OAuthError(f"Google token exchange failed: {resp.status_code}")
    data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        raise OAuthError("Google token response missing access_token")
    return access_token


async def fetch_userinfo(access_token: str) -> GoogleUserInfo:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        raise OAuthError(f"Google userinfo fetch failed: {resp.status_code}")
    data = resp.json()
    if not data.get("email_verified", False):
        raise OAuthError("Google email not verified")
    return GoogleUserInfo(
        sub=data["sub"],
        email=data["email"].lower(),
        name=data.get("name") or data["email"],
        picture=data.get("picture"),
    )


# ── User upsert + admin seeding ────────────────────────────────────────────

async def upsert_user(db: AsyncSession, info: GoogleUserInfo) -> tuple[User, bool]:
    """Returns (user, is_new). Server-side admin role assignment happens here:
    seed-list emails are always admin; everyone else starts as user."""
    env = get_settings()
    is_seed_admin = info.email in env.admin_seed_email_list

    result = await db.execute(select(User).where(User.google_sub == info.sub))
    user = result.scalar_one_or_none()
    is_new = False

    if user is None:
        # First login — create
        user = User(
            google_sub=info.sub,
            email=info.email,
            name=info.name,
            avatar_url=info.picture,
            role=UserRole.ADMIN if is_seed_admin else UserRole.USER,
            is_active=True,
            last_login=datetime.now(timezone.utc),
        )
        db.add(user)
        is_new = True
    else:
        if not user.is_active:
            raise OAuthError("Account is deactivated")
        user.email = info.email
        user.name = info.name
        user.avatar_url = info.picture
        user.last_login = datetime.now(timezone.utc)
        # Seed-list emails are forcibly admin every login — never demotable
        # without removing them from the seed list (documented in README).
        if is_seed_admin and user.role != UserRole.ADMIN:
            user.role = UserRole.ADMIN

    await db.commit()
    await db.refresh(user)
    return user, is_new


# ── JWT + refresh token issuance ───────────────────────────────────────────

@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    access_expires_in: int
    refresh_raw: str
    refresh_record_id: str


async def issue_tokens(db: AsyncSession, user: User) -> IssuedTokens:
    env = get_settings()
    access = create_access_token(
        user_id=user.id, email=user.email, role=user.role.value
    )
    refresh_raw = generate_refresh_token()
    record = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_raw),
        expires_at=refresh_token_expiry(),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return IssuedTokens(
        access_token=access,
        access_expires_in=env.jwt_access_token_minutes * 60,
        refresh_raw=refresh_raw,
        refresh_record_id=str(record.id),
    )


# ── Refresh rotation + revocation ──────────────────────────────────────────

async def rotate_refresh(db: AsyncSession, raw_token: str) -> tuple[User, IssuedTokens]:
    from app.core.security import verify_refresh_token

    # We can't index by raw token (it's hashed). Pull non-revoked, non-expired
    # rows in batches. For our scale (10s-100s of active sessions) this is fine.
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > now,
        )
    )
    rows = result.scalars().all()
    match: RefreshToken | None = None
    for row in rows:
        if verify_refresh_token(raw_token, row.token_hash):
            match = row
            break
    if match is None:
        raise OAuthError("Invalid or expired refresh token")

    # Rotate: revoke the old one immediately.
    match.revoked = True
    user_result = await db.execute(select(User).where(User.id == match.user_id))
    user = user_result.scalar_one()
    if not user.is_active:
        await db.commit()
        raise OAuthError("Account is deactivated")
    await db.commit()
    tokens = await issue_tokens(db, user)
    return user, tokens


async def revoke_refresh(db: AsyncSession, raw_token: str | None) -> None:
    if not raw_token:
        return
    from app.core.security import verify_refresh_token

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > now,
        )
    )
    for row in result.scalars().all():
        if verify_refresh_token(raw_token, row.token_hash):
            row.revoked = True
            await db.commit()
            return
