"""Declarative base + a JSONB-or-JSON column type that works on Postgres + SQLite."""
from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

# Use JSONB on Postgres for better indexing; fall back to JSON on SQLite.
JsonCol = JSONB().with_variant(JSON(), "sqlite")


class Base(DeclarativeBase):
    """Project-wide declarative base. All ORM models inherit from this."""
