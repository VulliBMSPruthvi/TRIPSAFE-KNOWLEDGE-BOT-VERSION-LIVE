from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class SystemPrompt(Base):
    """Versioned system prompts. Exactly one row has is_active=true.

    Admins update the active prompt via the Admin Portal; we keep the last 10
    versions for revert. Active prompt is read by rag.py on every /chat call.
    """

    __tablename__ = "system_prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
