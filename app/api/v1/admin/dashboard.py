"""Dashboard: total users, chats, active sessions, recent activity."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.activity_log import ActivityLog
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.admin import DashboardActivityItem, DashboardStats
from app.services.rag import engine as rag_engine

router = APIRouter()


@router.get("/dashboard", response_model=DashboardStats, summary="Aggregate stats")
async def get_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DashboardStats:
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_30m = now - timedelta(minutes=30)

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users = (
        await db.execute(select(func.count(User.id)).where(User.is_active.is_(True)))
    ).scalar_one()
    total_chats = (await db.execute(select(func.count(ChatMessage.id)))).scalar_one()
    chats_today = (
        await db.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.created_at >= day_start)
        )
    ).scalar_one()
    active_sessions = (
        await db.execute(
            select(func.count(func.distinct(ChatSession.id))).where(
                ChatSession.last_message_at >= cutoff_30m
            )
        )
    ).scalar_one()

    recent_q = (
        select(ActivityLog, User.email)
        .join(User, User.id == ActivityLog.user_id, isouter=True)
        .order_by(desc(ActivityLog.created_at))
        .limit(20)
    )
    recent_rows = (await db.execute(recent_q)).all()
    recent = [
        DashboardActivityItem(
            id=row[0].id,
            action_type=row[0].action_type,
            user_id=row[0].user_id,
            user_email=row[1],
            created_at=row[0].created_at,
        )
        for row in recent_rows
    ]

    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        total_chats=total_chats,
        chats_today=chats_today,
        active_sessions_30m=active_sessions,
        rag_index_loaded=rag_engine.available,
        rag_chunk_count=rag_engine.chunk_count,
        rag_loaded_at=rag_engine.loaded_at,
        recent_activity=recent,
    )
