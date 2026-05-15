from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Setting(Base):
    """Generic key/value store for admin-tunable runtime settings.

    Known keys (Phase B onward):
      - chat_model               → e.g. "claude-haiku-4-5"
      - google_oauth_client_id
      - google_oauth_client_secret  (stored as plaintext in DB; for true
        defense-in-depth, encrypt at rest at the DB level or move to
        Secrets Manager — tracked for Phase D hardening)
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
