"""Chat endpoints: send message, list own sessions, fetch session messages."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.system_prompt import SystemPrompt
from app.schemas.chat import (
    ChatMessagePublic,
    ChatRequest,
    ChatResponse,
    ChatSessionPublic,
    RetrievedChunk,
)
from app.services import settings_store
from app.services.activity import ActionType, log_action
from app.services.rag import engine as rag_engine

# NOTE: rate limiting on this route lands in Phase D as Starlette middleware.
# slowapi's decorator conflicts with FastAPI's Annotated-Depends signature
# introspection (https://github.com/laurentS/slowapi/issues/...).

logger = logging.getLogger("tripsafe.chat")
router = APIRouter()

HISTORY_TURNS = 20  # last N user+assistant messages forwarded as context

DEFAULT_SYSTEM_PROMPT = (
    "You are a knowledgeable TripSafe travel insurance assistant.\n\n"
    "How to read the retrieved context:\n"
    "- Each retrieved chunk begins with `Document:` and may include `Section:` "
    "and `Table:` headers, followed by either prose or a `Row:` line.\n"
    "- A `Row:` line is one table row in `Header: Value | Header: Value` form. "
    "Treat each value as belonging only to the plan / region / category named "
    "in the chunk's `Table:` or `Section:` header.\n\n"
    "Answering rules:\n"
    "1. For SINGLE-PRICE questions: find the one chunk that matches ALL of "
    "the user's constraints (plan, region, trip duration band, age band) and "
    "read the value off that row. Never average, interpolate, or pick a "
    "number from a different plan or region.\n"
    "2. For COMPARISON / 'all plans' / 'list every tier' questions: scan ALL "
    "retrieved chunks. If you find rows for several plans that share the "
    "user's region/duration/age constraints, list every one of them. Do NOT "
    "say 'I only have pricing for X and Y' unless you have genuinely "
    "scanned every retrieved chunk and confirmed the others are missing.\n"
    "3. If the user's constraints fall between two duration or age bands, "
    "say so explicitly and quote both bracketing values.\n"
    "4. If after scanning every retrieved chunk you still don't have the "
    "fact, say plainly: 'I don't have that specific figure in the knowledge "
    "base. Please check the source document directly.' Don't guess. But "
    "don't add this caveat when you do have the data.\n"
    "5. When you cite a number, also name the plan, region, age band and "
    "duration so the user can verify.\n"
    "6. Once you commit to an answer in a conversation, do not flip-flop on "
    "follow-up turns unless the user provides new evidence. If a user "
    "challenges you, re-check the retrieved chunks before changing position.\n"
    "7. Use the prior conversation history to interpret pronouns and "
    "follow-up questions ('it', 'that plan', 'tell me more').\n"
    "8. Be concise. Use markdown tables for comparisons and lists. Skip "
    "decorative emojis and excessive headings — answer the question.\n\n"
    "Be professional and helpful."
)


async def _get_active_system_prompt(db: AsyncSession) -> str:
    result = await db.execute(
        select(SystemPrompt)
        .where(SystemPrompt.is_active.is_(True))
        .order_by(desc(SystemPrompt.created_at))
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row.content if row else DEFAULT_SYSTEM_PROMPT


async def _get_or_create_session(
    db: AsyncSession, user_id: UUID, session_id: UUID | None
) -> ChatSession:
    if session_id is not None:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id, ChatSession.user_id == user_id
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    session = ChatSession(user_id=user_id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def _recent_history(
    db: AsyncSession, session_id: UUID, turns: int
) -> list[dict[str, str]]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(desc(ChatMessage.created_at))
        .limit(turns * 2)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return [{"role": m.role.value, "content": m.content} for m in rows]


@router.post("", response_model=ChatResponse, summary="Send a chat message")
async def post_chat(
    request: Request,
    payload: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> ChatResponse:
    if not rag_engine.available:
        raise HTTPException(
            status_code=503,
            detail=(
                "Knowledge base not built yet. An admin must upload source files "
                "and rebuild the index from the Admin Portal."
            ),
        )

    session = await _get_or_create_session(db, current_user.id, payload.session_id)
    history = await _recent_history(db, session.id, HISTORY_TURNS)
    retrieved = rag_engine.retrieve(payload.prompt)
    system_prompt = await _get_active_system_prompt(db)
    model = await settings_store.get_setting(db, "chat_model")
    if not model:
        raise HTTPException(status_code=500, detail="No chat_model configured")

    # Persist user message before the LLM call so we have a record even if
    # generation fails or times out.
    user_msg = ChatMessage(
        session_id=session.id,
        user_id=current_user.id,
        role=MessageRole.USER,
        content=payload.prompt,
    )
    db.add(user_msg)
    session.message_count += 1
    session.last_message_at = datetime.now(timezone.utc)
    await db.commit()

    try:
        answer = rag_engine.generate_answer(
            model=model,
            system_prompt=system_prompt,
            history=history,
            user_query=payload.prompt,
            retrieved=retrieved,
        )
    except Exception:
        logger.exception("claude_call_failed user_id=%s", current_user.id)
        raise HTTPException(
            status_code=502, detail="Upstream LLM error. Try again."
        ) from None

    assistant_msg = ChatMessage(
        session_id=session.id,
        user_id=current_user.id,
        role=MessageRole.ASSISTANT,
        content=answer,
        retrieved_chunks=[r.as_dict() for r in retrieved],
    )
    db.add(assistant_msg)
    session.message_count += 1
    session.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(assistant_msg)

    await log_action(
        db,
        action_type=ActionType.CHAT,
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        extra={
            "session_id": str(session.id),
            "model": model,
            "retrieved_count": len(retrieved),
        },
    )

    return ChatResponse(
        session_id=session.id,
        message_id=assistant_msg.id,
        content=answer,
        retrieved_chunks=[
            RetrievedChunk(source=r.source, text=r.text, distance=r.distance)
            for r in retrieved
        ],
        model=model,
    )


@router.get(
    "/sessions",
    response_model=list[ChatSessionPublic],
    summary="List the current user's chat sessions",
)
async def list_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    limit: int = 50,
) -> list[ChatSessionPublic]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(desc(ChatSession.last_message_at))
        .limit(min(limit, 200))
    )
    return [ChatSessionPublic.model_validate(s) for s in result.scalars().all()]


@router.post(
    "/stream",
    response_class=StreamingResponse,
    response_model=None,
    summary="Stream a chat response as Server-Sent Events",
)
async def post_chat_stream(
    request: Request,
    payload: ChatRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    if not rag_engine.available:
        raise HTTPException(
            status_code=503,
            detail=(
                "Knowledge base not built yet. An admin must upload source files "
                "and rebuild the index from the Admin Portal."
            ),
        )

    session = await _get_or_create_session(db, current_user.id, payload.session_id)
    history = await _recent_history(db, session.id, HISTORY_TURNS)
    retrieved = rag_engine.retrieve(payload.prompt)
    system_prompt = await _get_active_system_prompt(db)
    model = await settings_store.get_setting(db, "chat_model")
    if not model:
        raise HTTPException(status_code=500, detail="No chat_model configured")

    user_msg = ChatMessage(
        session_id=session.id,
        user_id=current_user.id,
        role=MessageRole.USER,
        content=payload.prompt,
    )
    db.add(user_msg)
    session.message_count += 1
    session.last_message_at = datetime.now(timezone.utc)
    await db.commit()

    chunks_payload = [r.as_dict() for r in retrieved]
    client_ip = request.client.host if request.client else None
    session_id = session.id
    user_id = current_user.id

    async def event_stream():
        from app.db.session import SessionLocal

        # Initial event: tells the client which session this is and surfaces
        # the retrieved sources immediately so the UI can render them.
        yield _sse({
            "type": "start",
            "session_id": str(session_id),
            "model": model,
            "sources": [{"source": c["source"], "distance": c["distance"]} for c in chunks_payload],
        })

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def produce():
            try:
                for delta in rag_engine.stream_answer(
                    model=model,
                    system_prompt=system_prompt,
                    history=history,
                    user_query=payload.prompt,
                    retrieved=retrieved,
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, delta)
            except Exception as exc:  # noqa: BLE001
                loop.call_soon_threadsafe(
                    queue.put_nowait, f"__ERROR__{exc!s}"
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        producer_task = asyncio.create_task(asyncio.to_thread(produce))

        collected: list[str] = []
        error: str | None = None
        while True:
            piece = await queue.get()
            if piece is None:
                break
            if piece.startswith("__ERROR__"):
                error = piece[len("__ERROR__"):]
                break
            collected.append(piece)
            yield _sse({"type": "delta", "text": piece})

        await producer_task

        if error:
            yield _sse({"type": "error", "detail": error})
            return

        full_text = "".join(collected).strip()

        # Persist the assistant message in a fresh session — the request session
        # may already be closed by the time we get here.
        async with SessionLocal() as bg_db:
            assistant = ChatMessage(
                session_id=session_id,
                user_id=user_id,
                role=MessageRole.ASSISTANT,
                content=full_text,
                retrieved_chunks=chunks_payload,
            )
            bg_db.add(assistant)
            sess_res = await bg_db.execute(
                select(ChatSession).where(ChatSession.id == session_id)
            )
            sess_row = sess_res.scalar_one_or_none()
            if sess_row is not None:
                sess_row.message_count += 1
                sess_row.last_message_at = datetime.now(timezone.utc)
            await bg_db.commit()
            await bg_db.refresh(assistant)
            assistant_id = str(assistant.id)

            await log_action(
                bg_db,
                action_type=ActionType.CHAT,
                user_id=user_id,
                ip_address=client_ip,
                extra={"session_id": str(session_id), "model": model, "stream": True},
            )

        yield _sse({"type": "done", "message_id": assistant_id})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessagePublic],
    summary="Fetch full transcript of one session",
)
async def get_session_messages(
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> list[ChatMessagePublic]:
    session_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    if session_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return [ChatMessagePublic.model_validate(m) for m in result.scalars().all()]
