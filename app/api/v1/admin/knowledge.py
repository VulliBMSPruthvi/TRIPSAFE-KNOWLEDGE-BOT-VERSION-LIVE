"""Knowledge Base: upload source files, list/delete them, trigger index rebuild."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import AdminUser
from app.db.session import SessionLocal, get_db
from app.models.index_build import IndexBuild, IndexBuildStatus
from app.models.knowledge_file import KnowledgeFile
from app.schemas.admin import (
    IndexBuildRow,
    IndexStatusResponse,
    KnowledgeFileRow,
)
from app.services import indexer, s3_store
from app.services.activity import ActionType, log_action
from app.services.rag import engine as rag_engine

router = APIRouter()

ALLOWED_EXTENSIONS = {".docx", ".csv"}
ALLOWED_MIME = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/csv",
    "application/csv",
    "application/octet-stream",  # browsers sometimes mislabel .csv
}
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB


# ── Files ───────────────────────────────────────────────────────────────

@router.get("/files", response_model=list[KnowledgeFileRow], summary="List source files")
async def list_files(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
) -> list[KnowledgeFileRow]:
    result = await db.execute(
        select(KnowledgeFile).order_by(desc(KnowledgeFile.uploaded_at))
    )
    return [KnowledgeFileRow.model_validate(f) for f in result.scalars().all()]


@router.post(
    "/files",
    response_model=KnowledgeFileRow,
    status_code=201,
    summary="Upload a new .docx or .csv source file",
)
async def upload_file(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminUser,
    file: UploadFile = File(...),
) -> KnowledgeFileRow:
    settings = get_settings()

    original = file.filename or ""
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Only {ALLOWED_EXTENSIONS} accepted")
    if file.content_type and file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400, detail=f"Unexpected MIME type: {file.content_type}"
        )

    uploads_dir = settings.uploads_path
    uploads_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = uploads_dir / stored_name

    # Stream to disk while enforcing the size cap.
    total = 0
    with stored_path.open("wb") as fh:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                fh.close()
                stored_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File exceeds 20 MB cap")
            fh.write(chunk)

    # Replace-on-upload semantics: if a file with the same name is already
    # active, retire the older row(s) AND delete their stored files so the
    # next index rebuild sees only the freshly uploaded version. This
    # matches the admin's mental model ("the list IS what gets indexed")
    # and prevents duplicate chunks like the user reported.
    existing_q = await db.execute(
        select(KnowledgeFile).where(
            KnowledgeFile.filename == original,
            KnowledgeFile.is_active.is_(True),
        )
    )
    for old in existing_q.scalars().all():
        old_path = Path(old.stored_path)
        try:
            old_path.unlink(missing_ok=True)
        except OSError:
            pass
        s3_store.delete_upload(old_path)
        await db.delete(old)

    record = KnowledgeFile(
        filename=original,
        stored_path=str(stored_path),
        file_size=total,
        content_type=file.content_type or "application/octet-stream",
        uploaded_by=admin.id,
        is_active=True,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    # Mirror to S3 so a container restart can't lose this file.
    s3_store.push_upload(stored_path)

    await log_action(
        db,
        action_type=ActionType.FILE_UPLOAD,
        user_id=admin.id,
        ip_address=request.client.host if request.client else None,
        extra={"file_id": str(record.id), "size_bytes": total},
    )
    return KnowledgeFileRow.model_validate(record)


@router.delete(
    "/files/{file_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    summary="Delete a source file",
)
async def delete_file(
    file_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminUser,
) -> Response:
    record = (
        await db.execute(select(KnowledgeFile).where(KnowledgeFile.id == file_id))
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")

    path = Path(record.stored_path)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
    s3_store.delete_upload(path)

    await db.delete(record)
    await db.commit()
    await log_action(
        db,
        action_type=ActionType.FILE_DELETE,
        user_id=admin.id,
        ip_address=request.client.host if request.client else None,
        extra={"file_id": str(file_id)},
    )
    return Response(status_code=204)


# ── Index status + rebuilds ─────────────────────────────────────────────

@router.get("/index/status", response_model=IndexStatusResponse, summary="Current index state")
async def index_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
) -> IndexStatusResponse:
    latest = (
        await db.execute(select(IndexBuild).order_by(desc(IndexBuild.started_at)).limit(1))
    ).scalar_one_or_none()
    return IndexStatusResponse(
        loaded=rag_engine.available,
        chunk_count=rag_engine.chunk_count,
        loaded_at=rag_engine.loaded_at,
        latest_build=IndexBuildRow.model_validate(latest) if latest else None,
    )


async def _run_index_build_isolated(build_id: UUID) -> None:
    """Background task runner. Uses its own DB session — the request-scoped
    session is gone by the time this fires."""
    async with SessionLocal() as db:
        await indexer.run_build(db, build_id)


@router.post(
    "/index/rebuild",
    response_model=IndexBuildRow,
    status_code=202,
    summary="Kick off a background index rebuild",
)
async def trigger_rebuild(
    request: Request,
    background: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminUser,
) -> IndexBuildRow:
    # Reject if a build is already in flight — prevents two concurrent rewrites.
    in_flight = (
        await db.execute(
            select(IndexBuild).where(
                IndexBuild.status.in_(
                    [IndexBuildStatus.PENDING, IndexBuildStatus.RUNNING]
                )
            )
        )
    ).scalar_one_or_none()
    if in_flight is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Build {in_flight.id} already in progress (status={in_flight.status.value})",
        )

    build = IndexBuild(
        triggered_by=admin.id,
        status=IndexBuildStatus.PENDING,
    )
    db.add(build)
    await db.commit()
    await db.refresh(build)

    await log_action(
        db,
        action_type=ActionType.INDEX_REBUILD,
        user_id=admin.id,
        ip_address=request.client.host if request.client else None,
        extra={"build_id": str(build.id)},
    )

    background.add_task(_run_index_build_isolated, build.id)
    return IndexBuildRow.model_validate(build)


@router.get(
    "/index/builds",
    response_model=list[IndexBuildRow],
    summary="History of past rebuilds",
)
async def list_builds(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: AdminUser,
    limit: int = 20,
) -> list[IndexBuildRow]:
    rows = await db.execute(
        select(IndexBuild).order_by(desc(IndexBuild.started_at)).limit(min(limit, 100))
    )
    return [IndexBuildRow.model_validate(b) for b in rows.scalars().all()]
