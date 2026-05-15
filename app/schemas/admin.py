from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.index_build import IndexBuildStatus
from app.models.user import UserRole


# ── Dashboard ───────────────────────────────────────────────────────────

class DashboardActivityItem(BaseModel):
    id: UUID
    action_type: str
    user_id: UUID | None
    user_email: str | None
    created_at: datetime


class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    total_chats: int
    chats_today: int
    active_sessions_30m: int
    rag_index_loaded: bool
    rag_chunk_count: int
    rag_loaded_at: str | None
    recent_activity: list[DashboardActivityItem]


# ── User management ─────────────────────────────────────────────────────

class AdminUserRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    name: str
    avatar_url: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: datetime | None


class RoleChangeRequest(BaseModel):
    role: UserRole


class ActiveChangeRequest(BaseModel):
    is_active: bool


# ── Chat logs ───────────────────────────────────────────────────────────

class ChatSessionWithUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    user_email: EmailStr
    user_name: str
    started_at: datetime
    last_message_at: datetime
    message_count: int


class ChatLogSearchHit(BaseModel):
    message_id: UUID
    session_id: UUID
    user_id: UUID
    user_email: EmailStr
    role: str
    content: str
    created_at: datetime


# ── Knowledge base ──────────────────────────────────────────────────────

class KnowledgeFileRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    file_size: int
    content_type: str
    uploaded_by: UUID | None
    uploaded_at: datetime
    is_active: bool


class IndexBuildRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    triggered_by: UUID | None
    status: IndexBuildStatus
    chunk_count: int | None
    source_files: list[dict[str, Any]] | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None


class IndexStatusResponse(BaseModel):
    loaded: bool
    chunk_count: int
    loaded_at: str | None
    latest_build: IndexBuildRow | None


# ── System prompt manager ───────────────────────────────────────────────

class SystemPromptRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    created_by: UUID | None
    created_at: datetime
    is_active: bool


class SystemPromptUpdate(BaseModel):
    content: str = Field(..., min_length=10, max_length=8000)


# ── Activity log ────────────────────────────────────────────────────────

class ActivityLogRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    user_email: str | None
    action_type: str
    extra: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


class ActivityLogPage(BaseModel):
    rows: list[ActivityLogRow]
    total: int
    page: int
    page_size: int


# ── Integrations (model dropdown + OAuth creds) ─────────────────────────

class ModelOption(BaseModel):
    value: str
    label: str
    description: str


class ChatModelSettings(BaseModel):
    current_model: str
    available_models: list[ModelOption]


class ChatModelUpdate(BaseModel):
    model: str


class GoogleOAuthSettings(BaseModel):
    client_id: str
    client_secret_set: bool
    redirect_uri: str


class GoogleOAuthUpdate(BaseModel):
    client_id: str = Field(..., min_length=10)
    client_secret: str = Field(..., min_length=10)
