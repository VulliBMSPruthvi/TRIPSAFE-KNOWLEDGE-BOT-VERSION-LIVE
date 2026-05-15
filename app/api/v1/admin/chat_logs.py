"""Chat logs viewer: browse, search, CSV export."""
from __future__ import annotations

import csv
import io
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AdminUser
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.admin import ChatLogSearchHit, ChatSessionWithUser
from app.schemas.chat import ChatMessagePublic

router = APIRouter()


@router.get(
    "/sessions",
    response_model=list[ChatSessionWithUser],
    summary="List all chat sessions, optionally filtered by user",
)
async def list_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
    user_id: UUID | None = None,
    limit: int = Query(50, le=200),
) -> list[ChatSessionWithUser]:
    q = (
        select(ChatSession, User)
        .join(User, User.id == ChatSession.user_id)
        .order_by(desc(ChatSession.last_message_at))
        .limit(limit)
    )
    if user_id is not None:
        q = q.where(ChatSession.user_id == user_id)
    rows = (await db.execute(q)).all()
    return [
        ChatSessionWithUser(
            id=s.id,
            user_id=u.id,
            user_email=u.email,
            user_name=u.name,
            started_at=s.started_at,
            last_message_at=s.last_message_at,
            message_count=s.message_count,
        )
        for s, u in rows
    ]


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessagePublic],
    summary="Full transcript of one session (admin view)",
)
async def session_messages(
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
) -> list[ChatMessagePublic]:
    session = (
        await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return [ChatMessagePublic.model_validate(m) for m in rows.scalars().all()]


@router.get(
    "/search",
    response_model=list[ChatLogSearchHit],
    summary="Keyword search across all chat messages",
)
async def search_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(100, le=500),
) -> list[ChatLogSearchHit]:
    like = f"%{q}%"
    query = (
        select(ChatMessage, User)
        .join(User, User.id == ChatMessage.user_id)
        .where(or_(ChatMessage.content.ilike(like)))
        .order_by(desc(ChatMessage.created_at))
        .limit(limit)
    )
    rows = (await db.execute(query)).all()
    return [
        ChatLogSearchHit(
            message_id=m.id,
            session_id=m.session_id,
            user_id=u.id,
            user_email=u.email,
            role=m.role.value,
            content=m.content,
            created_at=m.created_at,
        )
        for m, u in rows
    ]


@router.get(
    "/users/{user_id}/export.csv",
    response_class=StreamingResponse,
    response_model=None,
    summary="Export a user's full chat history as CSV",
)
async def export_user_chats(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
) -> StreamingResponse:
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    rows = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at)
        )
    ).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["timestamp_utc", "session_id", "role", "content"]
    )
    for m in rows:
        writer.writerow(
            [m.created_at.isoformat(), str(m.session_id), m.role.value, m.content]
        )
    buf.seek(0)
    safe_email = user.email.replace("@", "_at_").replace(".", "_")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="chat_export_{safe_email}.csv"'
        },
    )
