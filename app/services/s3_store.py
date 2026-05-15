"""S3 sync for FAISS index files.

App Runner containers have ephemeral local storage — if a container restarts
or scales out, any local-only FAISS files are lost. We persist them in S3 and
sync both directions:

  - **on_startup**: download the latest .faiss + .pkl from S3 into the
    container's local FAISS_INDEX_DIR (if they exist).
  - **after_rebuild**: upload the freshly-built .faiss + .pkl to S3 so the
    next container (or a horizontal scale-out replica) picks them up.

Disabled by default (USE_S3_FOR_FAISS=false). Production env var enables it.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import get_settings
from app.services.rag import INDEX_FILENAME, METADATA_FILENAME

logger = logging.getLogger("tripsafe.s3_store")


def _client():
    import boto3

    settings = get_settings()
    return boto3.client("s3", region_name=settings.aws_region)


def is_enabled() -> bool:
    settings = get_settings()
    return settings.use_s3_for_faiss and bool(settings.aws_s3_bucket)


def _key(filename: str) -> str:
    return get_settings().aws_s3_faiss_prefix.rstrip("/") + "/" + filename


def pull_to_local() -> bool:
    """Download S3 → local. Returns True if both files were pulled."""
    if not is_enabled():
        return False
    settings = get_settings()
    s3 = _client()
    local_dir = Path(settings.faiss_index_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    for name in (INDEX_FILENAME, METADATA_FILENAME):
        try:
            s3.download_file(settings.aws_s3_bucket, _key(name), str(local_dir / name))
            logger.info("s3_pulled file=%s", name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("s3_pull_failed file=%s err=%s", name, exc)
            ok = False
    return ok


def push_from_local() -> bool:
    """Upload local → S3. Returns True if both files were pushed."""
    if not is_enabled():
        return False
    settings = get_settings()
    s3 = _client()
    local_dir = Path(settings.faiss_index_dir)
    ok = True
    for name in (INDEX_FILENAME, METADATA_FILENAME):
        path = local_dir / name
        if not path.exists():
            logger.warning("s3_push_skipped missing=%s", name)
            ok = False
            continue
        try:
            s3.upload_file(str(path), settings.aws_s3_bucket, _key(name))
            logger.info("s3_pushed file=%s", name)
        except Exception as exc:  # noqa: BLE001
            logger.error("s3_push_failed file=%s err=%s", name, exc)
            ok = False
    return ok
