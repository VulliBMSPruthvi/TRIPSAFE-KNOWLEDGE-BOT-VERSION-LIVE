"""User management for admins."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AdminUser
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import (
    ActiveChangeRequest,
    AdminUserRow,
    RoleChangeRequest,
)
from app.services.activity import ActionType, log_action

router = APIRouter()


@router.get("", response_model=list[AdminUserRow], summary="List all users")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
) -> list[AdminUserRow]:
    result = await db.execute(select(User).order_by(desc(User.created_at)))
    return [AdminUserRow.model_validate(u) for u in result.scalars().all()]


@router.patch("/{user_id}/role", response_model=AdminUserRow, summary="Change user role")
async def change_role(
    user_id: UUID,
    payload: RoleChangeRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminUser,
) -> AdminUserRow:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    old_role = target.role
    target.role = payload.role
    await db.commit()
    await db.refresh(target)
    await log_action(
        db,
        action_type=ActionType.ROLE_CHANGE,
        user_id=admin.id,
        ip_address=request.client.host if request.client else None,
        extra={
            "target_user_id": str(user_id),
            "old_role": old_role.value,
            "new_role": payload.role.value,
        },
    )
    return AdminUserRow.model_validate(target)


@router.patch(
    "/{user_id}/active",
    response_model=AdminUserRow,
    summary="Deactivate or reactivate a user",
)
async def change_active(
    user_id: UUID,
    payload: ActiveChangeRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminUser,
) -> AdminUserRow:
    if user_id == admin.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = payload.is_active
    await db.commit()
    await db.refresh(target)
    await log_action(
        db,
        action_type=(
            ActionType.USER_REACTIVATE if payload.is_active else ActionType.USER_DEACTIVATE
        ),
        user_id=admin.id,
        ip_address=request.client.host if request.client else None,
        extra={"target_user_id": str(user_id)},
    )
    return AdminUserRow.model_validate(target)
