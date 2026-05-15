"""System prompt manager. Keeps the last 10 versions; only one is active."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AdminUser
from app.db.session import get_db
from app.models.system_prompt import SystemPrompt
from app.schemas.admin import SystemPromptRow, SystemPromptUpdate
from app.services.activity import ActionType, log_action

HISTORY_KEEP = 10

router = APIRouter()


@router.get(
    "/active",
    response_model=Optional[SystemPromptRow],
    summary="Current active prompt",
)
async def get_active(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
) -> Optional[SystemPromptRow]:
    row = (
        await db.execute(
            select(SystemPrompt)
            .where(SystemPrompt.is_active.is_(True))
            .order_by(desc(SystemPrompt.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    return SystemPromptRow.model_validate(row) if row else None


@router.get(
    "/history",
    response_model=list[SystemPromptRow],
    summary="Last N versions (newest first)",
)
async def get_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
) -> list[SystemPromptRow]:
    rows = await db.execute(
        select(SystemPrompt).order_by(desc(SystemPrompt.created_at)).limit(HISTORY_KEEP)
    )
    return [SystemPromptRow.model_validate(r) for r in rows.scalars().all()]


@router.post(
    "",
    response_model=SystemPromptRow,
    status_code=201,
    summary="Create new active prompt version",
)
async def create_version(
    payload: SystemPromptUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminUser,
) -> SystemPromptRow:
    # Deactivate all previous versions.
    await db.execute(update(SystemPrompt).values(is_active=False))
    new_row = SystemPrompt(content=payload.content, created_by=admin.id, is_active=True)
    db.add(new_row)
    await db.commit()
    await db.refresh(new_row)

    # Prune older versions beyond the keep-window.
    all_rows = (
        await db.execute(
            select(SystemPrompt).order_by(desc(SystemPrompt.created_at))
        )
    ).scalars().all()
    for stale in all_rows[HISTORY_KEEP:]:
        await db.delete(stale)
    await db.commit()

    await log_action(
        db,
        action_type=ActionType.PROMPT_UPDATE,
        user_id=admin.id,
        ip_address=request.client.host if request.client else None,
        extra={"prompt_id": str(new_row.id), "length": len(payload.content)},
    )
    return SystemPromptRow.model_validate(new_row)


@router.post(
    "/{prompt_id}/activate",
    response_model=SystemPromptRow,
    summary="Revert to an older version",
)
async def activate_version(
    prompt_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminUser,
) -> SystemPromptRow:
    from uuid import UUID

    try:
        target_id = UUID(prompt_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Bad prompt id") from exc

    target = (
        await db.execute(select(SystemPrompt).where(SystemPrompt.id == target_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Prompt version not found")

    await db.execute(update(SystemPrompt).values(is_active=False))
    target.is_active = True
    await db.commit()
    await db.refresh(target)
    await log_action(
        db,
        action_type=ActionType.PROMPT_UPDATE,
        user_id=admin.id,
        ip_address=request.client.host if request.client else None,
        extra={"reverted_to_prompt_id": str(target_id)},
    )
    return SystemPromptRow.model_validate(target)
