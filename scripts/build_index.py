"""Standalone CLI to rebuild the FAISS index from files in ./uploads/.

Useful for: initial setup before any admin exists, debugging, or running on a
machine without the API up. Uses the same chunking/embedding pipeline as the
admin "Rebuild Index" button so results are byte-identical.

Usage (inside the app container):
    docker compose exec app python -m scripts.build_index
"""
from __future__ import annotations

import asyncio
import pickle
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.index_build import IndexBuild, IndexBuildStatus
from app.models.knowledge_file import KnowledgeFile
from app.services.indexer import chunk_text, extract_text
from app.services.rag import (
    INDEX_FILENAME,
    METADATA_FILENAME,
    engine as rag_engine,
)


async def _list_active_files(db: AsyncSession) -> list[KnowledgeFile]:
    result = await db.execute(
        select(KnowledgeFile).where(KnowledgeFile.is_active.is_(True))
    )
    return list(result.scalars().all())


async def main() -> int:
    import faiss

    settings = get_settings()
    print(f"[build_index] uploads_dir={settings.uploads_path}")
    print(f"[build_index] faiss_dir={settings.faiss_index_path}")
    print(f"[build_index] embedding_model={settings.embedding_model}")

    async with SessionLocal() as db:
        files = await _list_active_files(db)
        if not files:
            # Fall back to scanning the uploads directory directly so this script
            # works even before any admin has uploaded via the API.
            print("[build_index] no KnowledgeFile rows; scanning uploads dir directly")
            on_disk = [
                p
                for p in settings.uploads_path.glob("*")
                if p.is_file() and p.suffix.lower() in {".docx", ".csv"}
            ]
            if not on_disk:
                print("[build_index] no .docx/.csv found — nothing to index", file=sys.stderr)
                return 1
            file_specs = [(p.name, p) for p in on_disk]
        else:
            file_specs = [(f.filename, Path(f.stored_path)) for f in files]

        all_chunks: list[tuple[str, str]] = []
        summary: list[dict[str, object]] = []
        for original_name, path in file_specs:
            if not path.exists():
                print(f"[build_index] missing on disk: {path}", file=sys.stderr)
                continue
            try:
                text = extract_text(path)
            except Exception as exc:  # noqa: BLE001
                print(f"[build_index] extract failed {original_name}: {exc}", file=sys.stderr)
                continue
            chunks = chunk_text(text, source=original_name)
            all_chunks.extend(chunks)
            summary.append({"filename": original_name, "chunks": len(chunks)})
            print(f"[build_index] {original_name}: {len(chunks)} chunks")

        if not all_chunks:
            print("[build_index] 0 chunks produced — aborting", file=sys.stderr)
            return 1

        texts = [c[0] for c in all_chunks]
        sources = [c[1] for c in all_chunks]

        print(f"[build_index] embedding {len(texts)} chunks…")
        embedder = rag_engine._get_embedder()  # noqa: SLF001
        embeddings = embedder.encode(
            texts, convert_to_numpy=True, batch_size=32, show_progress_bar=True
        ).astype("float32")

        dim = int(embeddings.shape[1])
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings)

        idx_dir = settings.faiss_index_path
        idx_dir.mkdir(parents=True, exist_ok=True)
        live_index = idx_dir / INDEX_FILENAME
        live_meta = idx_dir / METADATA_FILENAME
        faiss.write_index(index, str(live_index))
        with live_meta.open("wb") as fh:
            pickle.dump({"texts": texts, "sources": sources}, fh)
        print(f"[build_index] wrote {live_index} and {live_meta}")

        # Record the build in DB for auditability.
        build = IndexBuild(
            id=uuid.uuid4(),
            triggered_by=None,
            status=IndexBuildStatus.COMPLETE,
            chunk_count=len(all_chunks),
            source_files=summary,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(build)
        await db.commit()

    rag_engine.reload()
    print(f"[build_index] done. chunks={rag_engine.chunk_count}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
