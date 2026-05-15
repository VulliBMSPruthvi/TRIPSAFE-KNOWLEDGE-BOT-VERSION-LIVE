"""Admin router aggregation. Every sub-router is admin-only (server-side check).

A non-admin hitting /api/v1/admin/* gets HTTP 403 — never a redirect, never a
silent 404. Admin role is verified on every single request via `admin_required`.
"""
from fastapi import APIRouter, Depends

from app.core.dependencies import admin_required

from app.api.v1.admin import (
    activity_log,
    chat_logs,
    dashboard,
    integrations,
    knowledge,
    prompts,
    users,
)

# `dependencies=[Depends(admin_required)]` runs the admin check before any route
# matches, even before path resolution within sub-routers.
router = APIRouter(dependencies=[Depends(admin_required)])

router.include_router(dashboard.router, tags=["admin:dashboard"])
router.include_router(users.router, prefix="/users", tags=["admin:users"])
router.include_router(chat_logs.router, prefix="/chats", tags=["admin:chats"])
router.include_router(knowledge.router, prefix="/knowledge", tags=["admin:knowledge"])
router.include_router(prompts.router, prefix="/prompts", tags=["admin:prompts"])
router.include_router(integrations.router, prefix="/integrations", tags=["admin:integrations"])
router.include_router(activity_log.router, prefix="/activity", tags=["admin:activity"])
