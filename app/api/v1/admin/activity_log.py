"""Activity log: paginated, filterable audit trail."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AdminUser
from app.db.session import get_db
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.schemas.admin import ActivityLogPage, ActivityLogRow

router = APIRouter()

PAGE_SIZE = 50


@router.get("", response_model=ActivityLogPage, summary="Paginated activity log")
async def list_activity(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
    page: int = Query(1, ge=1),
    user_id: UUID | None = None,
    action_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> ActivityLogPage:
    filters = []
    if user_id is not None:
        filters.append(ActivityLog.user_id == user_id)
    if action_type:
        filters.append(ActivityLog.action_type == action_type)
    if since:
        filters.append(ActivityLog.created_at >= since)
    if until:
        filters.append(ActivityLog.created_at <= until)

    total = (await db.execute(select(func.count(ActivityLog.id)).where(*filters))).scalar_one()

    q = (
        select(ActivityLog, User.email)
        .join(User, User.id == ActivityLog.user_id, isouter=True)
        .where(*filters)
        .order_by(desc(ActivityLog.created_at))
        .limit(PAGE_SIZE)
        .offset((page - 1) * PAGE_SIZE)
    )
    rows = (await db.execute(q)).all()
    return ActivityLogPage(
        rows=[
            ActivityLogRow(
                id=row[0].id,
                user_id=row[0].user_id,
                user_email=row[1],
                action_type=row[0].action_type,
                extra=row[0].extra,
                ip_address=row[0].ip_address,
                created_at=row[0].created_at,
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=PAGE_SIZE,
    )
