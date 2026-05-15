"""DB-backed key/value settings with simple in-process cache.

Known keys:
  - chat_model                  → current Claude model name
  - google_oauth_client_id      → admin-managed OAuth client id (overrides env)
  - google_oauth_client_secret  → admin-managed OAuth client secret (overrides env)

Reads go through `get_setting`; writes through `set_setting`. The cache is
invalidated on every write, so the admin panel can change the model and the
next chat call picks it up with no restart.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.setting import Setting

_cache: dict[str, str] = {}
_lock = asyncio.Lock()


async def get_setting(db: AsyncSession, key: str, default: str | None = None) -> str | None:
    if key in _cache:
        return _cache[key]
    async with _lock:
        if key in _cache:
            return _cache[key]
        result = await db.execute(select(Setting).where(Setting.key == key))
        row = result.scalar_one_or_none()
        if row is None:
            return default
        _cache[key] = row.value
        return row.value


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    result = await db.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    await db.commit()
    _cache[key] = value


def invalidate_cache() -> None:
    _cache.clear()


async def seed_defaults(db: AsyncSession) -> None:
    """Ensure required settings rows exist on first boot."""
    settings = get_settings()
    defaults = {
        "chat_model": settings.default_chat_model,
    }
    for key, value in defaults.items():
        existing = await db.execute(select(Setting).where(Setting.key == key))
        if existing.scalar_one_or_none() is None:
            db.add(Setting(key=key, value=value))
    await db.commit()
