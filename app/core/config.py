"""Application settings, loaded exclusively from environment variables.

Never put secrets in this file. pydantic-settings reads from .env in dev and
from real env vars (injected by AWS Secrets Manager → ECS task def) in prod.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_secret_key: SecretStr = Field(..., min_length=16)
    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"

    # ── JWT ─────────────────────────────────────────────────────
    jwt_secret: SecretStr = Field(..., min_length=16)
    # Long-lived access token so users aren't kicked out mid-day.
    # Refresh token is even longer so closing the laptop overnight stays logged in.
    jwt_access_token_minutes: int = 1440  # 24h
    jwt_refresh_token_days: int = 30
    jwt_algorithm: str = "HS256"

    # ── Database ────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./tripsafe_dev.db"

    # ── Redis ───────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Anthropic ───────────────────────────────────────────────
    anthropic_api_key: SecretStr = SecretStr("")
    # Sonnet is materially better at synthesis and at not hallucinating when
    # the retrieved context is ambiguous. Haiku stays available as a fast/
    # cheap toggle in Admin → Integrations.
    default_chat_model: str = "claude-sonnet-4-6"

    # ── Google OAuth (bootstrap — admins can override via DB) ──
    google_oauth_client_id: str = ""
    google_oauth_client_secret: SecretStr = SecretStr("")
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ── Admin seed ──────────────────────────────────────────────
    admin_seed_emails: str = ""

    # ── RAG ─────────────────────────────────────────────────────
    faiss_index_dir: str = "./faiss_store"
    uploads_dir: str = "./uploads"
    # "local" = sentence-transformers running in-container (free, private, slow first run).
    # "openai" = OpenAI's embedding API. Used ONLY for embeddings — Claude still handles chat.
    embedding_provider: Literal["local", "openai"] = "local"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_api_key: SecretStr = SecretStr("")
    openai_embedding_model: str = "text-embedding-3-small"
    # K must be large enough to fit ALL plan-rows for a comparison query
    # (e.g. "compare all 6 plans for Asia, 15-21 days, 0-40 yrs" needs 6+
    # row chunks plus a few prose chunks). K=60 covers those cases comfortably
    # and adds ~3K tokens to the prompt — cheap for Sonnet.
    rag_top_k: int = 60

    # ── CORS ────────────────────────────────────────────────────
    cors_allowed_origins: str = "http://localhost:5173"

    # ── Rate limiting ───────────────────────────────────────────
    rate_limit_chat: str = "30/minute"
    rate_limit_auth: str = "10/minute"

    # ── AWS (production) ────────────────────────────────────────
    aws_region: str = "ap-south-1"
    aws_s3_bucket: str = ""
    aws_s3_faiss_prefix: str = "faiss/"
    aws_s3_uploads_prefix: str = "uploads/"
    aws_secrets_manager_prefix: str = "tripsafe/prod/"
    # When true, the RAG engine syncs the FAISS index files between local
    # ephemeral storage and S3 on startup + after every rebuild.
    use_s3_for_faiss: bool = False
    # When true, uploaded source documents are persisted to S3 on upload and
    # fetched back to local /uploads on demand. This means container restarts
    # no longer wipe the knowledge base.
    use_s3_for_uploads: bool = False

    # ── Frontend static serving (production) ────────────────────
    frontend_dist_dir: str = "/app/frontend_dist"

    # ── Computed helpers ────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def admin_seed_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_seed_emails.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def faiss_index_path(self) -> Path:
        return Path(self.faiss_index_dir)

    @property
    def uploads_path(self) -> Path:
        return Path(self.uploads_dir)

    @field_validator("cors_allowed_origins")
    @classmethod
    def _no_wildcard_in_prod(cls, v: str) -> str:
        # Wildcard CORS is forbidden in production. Field validators run before
        # the dependent app_env field is bound, so the runtime check is in
        # main.py at startup. Here we just refuse "*" outright.
        if v.strip() == "*":
            raise ValueError("CORS_ALLOWED_ORIGINS must not be '*' — list explicit origins.")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
