"""Import all ORM models here so Alembic's autogenerate sees them."""
from app.models.activity_log import ActivityLog
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.index_build import IndexBuild, IndexBuildStatus
from app.models.knowledge_file import KnowledgeFile
from app.models.refresh_token import RefreshToken
from app.models.setting import Setting
from app.models.system_prompt import SystemPrompt
from app.models.user import User, UserRole

__all__ = [
    "ActivityLog",
    "ChatMessage",
    "ChatSession",
    "IndexBuild",
    "IndexBuildStatus",
    "KnowledgeFile",
    "MessageRole",
    "RefreshToken",
    "Setting",
    "SystemPrompt",
    "User",
    "UserRole",
]
