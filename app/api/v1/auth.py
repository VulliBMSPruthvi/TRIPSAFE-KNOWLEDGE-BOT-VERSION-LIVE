"""Google SSO + JWT endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import ACCESS_COOKIE_NAME, CurrentUser
from app.db.session import get_db
from app.schemas.auth import TokenResponse, UserPublic
from app.services import auth as auth_service
from app.services.activity import ActionType, log_action

# NOTE: rate limiting on /auth/* lands in Phase D as Starlette middleware.

REFRESH_COOKIE_NAME = "ts_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"

router = APIRouter()


def _set_auth_cookies(
    response: JSONResponse | RedirectResponse,
    *,
    access_token: str,
    access_expires_in: int,
    refresh_raw: str,
) -> None:
    settings = get_settings()
    secure = settings.is_production
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=access_expires_in,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_raw,
        max_age=settings.jwt_refresh_token_days * 86400,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_auth_cookies(response: JSONResponse | RedirectResponse) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


@router.get(
    "/google/login",
    response_class=RedirectResponse,
    response_model=None,
    summary="Redirect to Google for SSO",
)
async def google_login(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    try:
        cfg = await auth_service.get_oauth_config(db)
    except auth_service.OAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    state = auth_service.make_state()
    url = auth_service.build_authorize_url(cfg, state)
    return RedirectResponse(url, status_code=307)


@router.get(
    "/google/callback",
    response_class=RedirectResponse,
    response_model=None,
    summary="Handle Google OAuth redirect",
)
async def google_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    if error:
        await log_action(
            db,
            action_type=ActionType.LOGIN_FAILED,
            ip_address=request.client.host if request.client else None,
            extra={"reason": "google_error", "error": error},
        )
        raise HTTPException(status_code=400, detail=f"Google returned: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        auth_service.verify_state(state)
        cfg = await auth_service.get_oauth_config(db)
        google_access = await auth_service.exchange_code(cfg, code)
        info = await auth_service.fetch_userinfo(google_access)
        user, is_new = await auth_service.upsert_user(db, info)
        tokens = await auth_service.issue_tokens(db, user)
    except auth_service.OAuthError as exc:
        await log_action(
            db,
            action_type=ActionType.LOGIN_FAILED,
            ip_address=request.client.host if request.client else None,
            extra={"reason": "oauth_error"},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await log_action(
        db,
        action_type=ActionType.SIGNUP if is_new else ActionType.LOGIN,
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        extra={"role": user.role.value, "new": is_new},
    )

    response = RedirectResponse(url=settings.frontend_base_url, status_code=307)
    _set_auth_cookies(
        response,
        access_token=tokens.access_token,
        access_expires_in=tokens.access_expires_in,
        refresh_raw=tokens.refresh_raw,
    )
    return response


@router.post(
    "/refresh",
    response_class=JSONResponse,
    response_model=None,
    summary="Rotate refresh token, get new access token",
)
async def refresh(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    ts_refresh: Annotated[str | None, Cookie()] = None,
) -> JSONResponse:
    if not ts_refresh:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        user, tokens = await auth_service.rotate_refresh(db, ts_refresh)
    except auth_service.OAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    await log_action(
        db,
        action_type=ActionType.REFRESH,
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )

    body = TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.access_expires_in,
        user=UserPublic.model_validate(user),
    ).model_dump(mode="json")
    response = JSONResponse(content=body)
    _set_auth_cookies(
        response,
        access_token=tokens.access_token,
        access_expires_in=tokens.access_expires_in,
        refresh_raw=tokens.refresh_raw,
    )
    return response


@router.post(
    "/logout",
    response_class=JSONResponse,
    response_model=None,
    summary="Revoke refresh token, clear cookies",
)
async def logout(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    ts_refresh: Annotated[str | None, Cookie()] = None,
) -> JSONResponse:
    await auth_service.revoke_refresh(db, ts_refresh)
    await log_action(
        db,
        action_type=ActionType.LOGOUT,
        ip_address=request.client.host if request.client else None,
    )
    response = JSONResponse(content={"status": "logged_out"})
    _clear_auth_cookies(response)
    return response


@router.get("/me", response_model=UserPublic, summary="Current user profile")
async def me(current_user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(current_user)
