from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base, JsonCol


class IndexBuildStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class IndexBuild(Base):
    __tablename__ = "index_builds"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[IndexBuildStatus] = mapped_column(
        SAEnum(
            IndexBuildStatus,
            name="index_build_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=IndexBuildStatus.PENDING,
        nullable=False,
        index=True,
    )
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_files: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonCol, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
