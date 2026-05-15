"""Audit-log writer. Never include PII (emails, raw chat content) in `extra`."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog


class ActionType:
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    SIGNUP = "SIGNUP"
    REFRESH = "REFRESH"
    CHAT = "CHAT"
    FILE_UPLOAD = "FILE_UPLOAD"
    FILE_DELETE = "FILE_DELETE"
    INDEX_REBUILD = "INDEX_REBUILD"
    PROMPT_UPDATE = "PROMPT_UPDATE"
    MODEL_CHANGE = "MODEL_CHANGE"
    ROLE_CHANGE = "ROLE_CHANGE"
    USER_DEACTIVATE = "USER_DEACTIVATE"
    USER_REACTIVATE = "USER_REACTIVATE"
    OAUTH_CONFIG_UPDATE = "OAUTH_CONFIG_UPDATE"


async def log_action(
    db: AsyncSession,
    *,
    action_type: str,
    user_id: UUID | None = None,
    ip_address: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    db.add(
        ActivityLog(
            user_id=user_id,
            action_type=action_type,
            ip_address=ip_address,
            extra=extra,
        )
    )
    await db.commit()
