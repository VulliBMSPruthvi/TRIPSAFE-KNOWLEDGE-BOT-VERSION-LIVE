"""FastAPI application factory.

Phase A: configuration, CORS, security headers, /health.
Routers and startup hooks for RAG / OAuth wire in during Phases B–C.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1 import api_router
from app.core.config import Settings, get_settings

logger = logging.getLogger("tripsafe")
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)


# ── Rate limiter (used by /auth and /chat in Phase B) ─────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan: validates config, seeds defaults, warms FAISS ───────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    _enforce_production_invariants(settings)

    # Seed default settings rows + try to load FAISS index (non-fatal).
    from datetime import datetime, timezone

    from sqlalchemy import select, update

    from app.db.session import SessionLocal
    from app.models.index_build import IndexBuild, IndexBuildStatus
    from app.services import s3_store, settings_store
    from app.services.rag import engine as rag_engine

    # Production: pull the latest FAISS index from S3 before loading.
    # No-op in dev (USE_S3_FOR_FAISS=false).
    if s3_store.is_enabled():
        s3_store.pull_to_local()

    async with SessionLocal() as db:
        await settings_store.seed_defaults(db)
        # Reap zombie builds: any pending/running rows are orphaned because
        # background tasks don't survive container restarts.
        stale = await db.execute(
            select(IndexBuild.id).where(
                IndexBuild.status.in_(
                    [IndexBuildStatus.PENDING, IndexBuildStatus.RUNNING]
                )
            )
        )
        stale_ids = [r[0] for r in stale.all()]
        if stale_ids:
            await db.execute(
                update(IndexBuild)
                .where(IndexBuild.id.in_(stale_ids))
                .values(
                    status=IndexBuildStatus.FAILED,
                    error_message="Container restarted while build was in progress.",
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.info("reaped_zombie_builds count=%d", len(stale_ids))

    loaded = rag_engine.reload()
    logger.info(
        "startup_complete env=%s rag_index_loaded=%s", settings.app_env, loaded
    )
    yield
    logger.info("shutdown")


def _enforce_production_invariants(settings: Settings) -> None:
    """Refuse to boot if production-only safety rules are violated."""
    if not settings.is_production:
        return
    problems: list[str] = []
    if "*" in settings.cors_origin_list:
        problems.append("CORS wildcard not allowed in production")
    if settings.app_debug:
        problems.append("APP_DEBUG must be false in production")
    if not settings.app_base_url.startswith("https://"):
        problems.append("APP_BASE_URL must be HTTPS in production")
    if settings.app_secret_key.get_secret_value() in {"", "change-me-to-a-long-random-string"}:
        problems.append("APP_SECRET_KEY must be set to a real secret in production")
    if settings.jwt_secret.get_secret_value() in {"", "change-me-to-a-different-long-random-string"}:
        problems.append("JWT_SECRET must be set to a real secret in production")
    # Production image is slim — sentence-transformers/torch aren't installed.
    # OpenAI is the only supported embedding provider in prod.
    if settings.embedding_provider != "openai":
        problems.append(
            "EMBEDDING_PROVIDER must be 'openai' in production "
            "(the slim prod image doesn't ship sentence-transformers)"
        )
    if not settings.openai_api_key.get_secret_value():
        problems.append("OPENAI_API_KEY must be set in production")
    if problems:
        raise RuntimeError("Refusing to start: " + "; ".join(problems))


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="TripSafe Knowledge Bot v2",
        description="Internal RAG chatbot for TripSafe travel insurance.",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── State shared across deps (rate limiter handle) ────────────────
    app.state.limiter = limiter
    app.state.settings = settings

    # ── CORS: explicit origin whitelist; no wildcards ─────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    # ── Security headers middleware ───────────────────────────────────
    # Swagger UI / ReDoc need to load JS+CSS from jsdelivr; we relax CSP for
    # the docs paths only. Everything else gets the strict default-src 'none'.
    DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if request.url.path in DOCS_PATHS or request.url.path.startswith("/docs"):
            # Permissive CSP for Swagger UI assets from jsdelivr CDN.
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
            )
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    # ── Rate-limit error handler ──────────────────────────────────────
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please slow down."},
        )

    # ── Routers ───────────────────────────────────────────────────────
    app.include_router(api_router)

    # ── Health (no auth, no rate limit) ───────────────────────────────
    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "env": settings.app_env,
            "version": app.version,
        }

    # ── Frontend static serving (production only) ─────────────────────
    # The Vite-built React app is copied into the image at /app/frontend_dist.
    # We mount /assets/* directly and route every non-/api path to index.html
    # so React Router can handle client-side routing (e.g. /admin/users).
    frontend_dir = Path(settings.frontend_dist_dir)
    if frontend_dir.is_dir() and (frontend_dir / "index.html").exists():
        assets_dir = frontend_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        index_html = frontend_dir / "index.html"

        @app.get("/", include_in_schema=False)
        async def root_index() -> FileResponse:
            return FileResponse(str(index_html))

        # SPA fallback — must be registered LAST so it doesn't shadow /api/* or /health.
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> Response:
            # Hard-block any prefix that should not fall through to React.
            if full_path.startswith(("api/", "docs", "openapi.json", "health", "assets/")):
                return Response(status_code=404)
            # Serve real files from frontend_dist (favicon, manifest, etc.)
            candidate = frontend_dir / full_path
            if candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(index_html))

    return app


app = create_app()
