from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat import MessageRole


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    session_id: UUID | None = Field(
        default=None,
        description="Existing session to append to. If null, a new session is created.",
    )


class RetrievedChunk(BaseModel):
    source: str
    text: str
    distance: float


class ChatResponse(BaseModel):
    session_id: UUID
    message_id: UUID
    content: str
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    model: str


class ChatMessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    retrieved_chunks: list[dict[str, Any]] | None = None
    created_at: datetime


class ChatSessionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    started_at: datetime
    last_message_at: datetime
    message_count: int
