"""Integrations: Claude model dropdown + Google OAuth credential management."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import AdminUser
from app.db.session import get_db
from app.schemas.admin import (
    ChatModelSettings,
    ChatModelUpdate,
    GoogleOAuthSettings,
    GoogleOAuthUpdate,
    ModelOption,
)
from app.services import settings_store
from app.services.activity import ActionType, log_action

router = APIRouter()

AVAILABLE_MODELS: list[ModelOption] = [
    ModelOption(
        value="claude-haiku-4-5",
        label="Claude Haiku 4.5 (recommended)",
        description="Fast, low-cost. Best price/performance for RAG-grounded answers.",
    ),
    ModelOption(
        value="claude-sonnet-4-6",
        label="Claude Sonnet 4.6",
        description="Stronger reasoning. ~5× the cost of Haiku.",
    ),
    ModelOption(
        value="claude-opus-4-7",
        label="Claude Opus 4.7",
        description="Highest quality. Reserve for hard cases — ~15× the cost of Haiku.",
    ),
]
ALLOWED_VALUES = {m.value for m in AVAILABLE_MODELS}


# ── Chat model ──────────────────────────────────────────────────────────

@router.get("/model", response_model=ChatModelSettings, summary="Current model + options")
async def get_model(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
) -> ChatModelSettings:
    current = await settings_store.get_setting(db, "chat_model")
    if not current:
        current = get_settings().default_chat_model
    return ChatModelSettings(current_model=current, available_models=AVAILABLE_MODELS)


@router.patch("/model", response_model=ChatModelSettings, summary="Switch active model")
async def update_model(
    payload: ChatModelUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminUser,
) -> ChatModelSettings:
    if payload.model not in ALLOWED_VALUES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model. Allowed: {sorted(ALLOWED_VALUES)}",
        )
    await settings_store.set_setting(db, "chat_model", payload.model)
    await log_action(
        db,
        action_type=ActionType.MODEL_CHANGE,
        user_id=admin.id,
        ip_address=request.client.host if request.client else None,
        extra={"new_model": payload.model},
    )
    return ChatModelSettings(current_model=payload.model, available_models=AVAILABLE_MODELS)


# ── Google OAuth credentials ────────────────────────────────────────────

@router.get("/google", response_model=GoogleOAuthSettings, summary="Current OAuth config")
async def get_oauth(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
) -> GoogleOAuthSettings:
    env = get_settings()
    client_id = (
        await settings_store.get_setting(db, "google_oauth_client_id")
    ) or env.google_oauth_client_id
    secret = (
        await settings_store.get_setting(db, "google_oauth_client_secret")
    ) or env.google_oauth_client_secret.get_secret_value()
    return GoogleOAuthSettings(
        client_id=client_id or "",
        client_secret_set=bool(secret),
        redirect_uri=env.google_oauth_redirect_uri,
    )


@router.patch(
    "/google",
    response_model=GoogleOAuthSettings,
    summary="Update Google OAuth client credentials",
)
async def update_oauth(
    payload: GoogleOAuthUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminUser,
) -> GoogleOAuthSettings:
    await settings_store.set_setting(db, "google_oauth_client_id", payload.client_id)
    await settings_store.set_setting(db, "google_oauth_client_secret", payload.client_secret)
    await log_action(
        db,
        action_type=ActionType.OAUTH_CONFIG_UPDATE,
        user_id=admin.id,
        ip_address=request.client.host if request.client else None,
        # Never log the secret itself; just note it was updated.
        extra={"client_id_last4": payload.client_id[-4:]},
    )
    env = get_settings()
    return GoogleOAuthSettings(
        client_id=payload.client_id,
        client_secret_set=True,
        redirect_uri=env.google_oauth_redirect_uri,
    )
