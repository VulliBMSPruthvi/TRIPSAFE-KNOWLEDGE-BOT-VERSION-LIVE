"""RAG engine: embeddings + FAISS retrieval + Claude generation.

The index files (`*.faiss` + `*.pkl`) live under settings.faiss_index_dir.
A singleton `_engine` holds the loaded objects in memory so /chat requests
don't pay the load cost. Admin's "Rebuild Index" trigger (Phase C) calls
`reload()` to swap them in atomically without restarting the process.

If no index exists yet, `available` returns False and /chat surfaces a clear
"knowledge base not built yet" error to the caller.
"""
from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger("tripsafe.rag")

INDEX_FILENAME = "trip_safe_index.faiss"
METADATA_FILENAME = "trip_safe_metadata.pkl"


@dataclass
class Retrieved:
    text: str
    source: str
    distance: float

    def as_dict(self) -> dict[str, Any]:
        return {"text": self.text, "source": self.source, "distance": self.distance}


class RagEngine:
    def __init__(self) -> None:
        self._lock = RLock()
        self._embedder: Any | None = None
        self._index: Any | None = None
        self._metadata: dict[str, list[str]] | None = None
        self._anthropic: Any | None = None
        self._loaded_at: str | None = None
        # mtime of the .faiss file at the moment we loaded it. Used to detect
        # that another worker (or our own indexer) wrote a newer index to disk,
        # so /chat sees fresh data without a process restart.
        self._index_mtime: float | None = None

    # ── Lazy initializers ────────────────────────────────────────────────

    def _get_embedder(self) -> Any:
        if self._embedder is None:
            # Corporate-network workaround: when behind a TLS-intercepting proxy
            # (e.g. Zscaler), huggingface_hub's TLS handshake fails. Set
            # EMBEDDING_DISABLE_SSL=true in .env to disable cert verification
            # for huggingface_hub downloads. Never set in production.
            import os

            if os.environ.get("EMBEDDING_DISABLE_SSL", "false").lower() == "true":
                import ssl

                import urllib3
                import requests
                from requests.adapters import HTTPAdapter

                ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001
                urllib3.disable_warnings()

                # Force every requests.Session.send to skip verification —
                # this is what huggingface_hub uses for model downloads.
                _orig_send = HTTPAdapter.send

                def _patched_send(self, request, **kwargs):  # type: ignore[no-untyped-def]
                    kwargs["verify"] = False
                    return _orig_send(self, request, **kwargs)

                HTTPAdapter.send = _patched_send  # type: ignore[method-assign]
                logger.warning("embedder_ssl_verification_disabled (dev only)")

            from sentence_transformers import SentenceTransformer

            settings = get_settings()
            logger.info("loading_embedder model=%s", settings.embedding_model)
            self._embedder = SentenceTransformer(settings.embedding_model)
        return self._embedder

    def _get_anthropic(self) -> Any:
        if self._anthropic is None:
            from anthropic import Anthropic

            key = get_settings().anthropic_api_key.get_secret_value()
            if not key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. Add it to .env and restart."
                )
            self._anthropic = Anthropic(api_key=key)
        return self._anthropic

    # ── FAISS load / hot reload ──────────────────────────────────────────

    @property
    def available(self) -> bool:
        # Multi-worker safety: under gunicorn we run >1 worker process per
        # container. A rebuild only mutates ONE worker's memory; the others
        # still see stale (or empty) singletons. Two cases to handle:
        #
        #   (a) In-memory is empty → pull from S3 if enabled, then load disk.
        #   (b) In-memory is populated but a NEWER index exists on disk
        #       (because another worker rebuilt it) → reload from disk.
        try:
            from app.services import s3_store
            from app.core.config import get_settings as _gs

            settings = _gs()
            local_index = settings.faiss_index_path / INDEX_FILENAME

            if self._index is None or self._metadata is None:
                # Case (a): cold cache. Try S3 first so we benefit from any
                # rebuild a sibling worker pushed up there.
                try:
                    if s3_store.is_enabled():
                        s3_store.pull_to_local()
                except Exception:
                    logger.exception("s3_pull_on_demand_failed")
                self.reload()
            elif local_index.exists():
                # Case (b): warm cache. Cheap check — if disk has a newer
                # .faiss than what we loaded, reload. This is how the admin
                # "Rebuild Index" propagates to all workers without a
                # restart, even though Python singletons are per-process.
                disk_mtime = local_index.stat().st_mtime
                if (
                    self._index_mtime is None
                    or disk_mtime > self._index_mtime + 0.5  # 0.5s slack
                ):
                    logger.info(
                        "faiss_disk_newer_reloading disk=%s loaded=%s",
                        disk_mtime,
                        self._index_mtime,
                    )
                    self.reload()
        except Exception:
            logger.exception("rag_availability_check_failed")

        return self._index is not None and self._metadata is not None

    @property
    def chunk_count(self) -> int:
        if self._metadata is None:
            return 0
        return len(self._metadata.get("texts", []))

    @property
    def loaded_at(self) -> str | None:
        return self._loaded_at

    def reload(self) -> bool:
        """Load FAISS index + metadata from disk. Returns True on success.
        On failure (no files yet, corrupt), keeps the previously-loaded
        index in place — the caller's job is to log and notify the admin."""
        import faiss

        settings = get_settings()
        index_path = settings.faiss_index_path / INDEX_FILENAME
        meta_path = settings.faiss_index_path / METADATA_FILENAME

        if not index_path.exists() or not meta_path.exists():
            logger.warning(
                "faiss_assets_missing index=%s meta=%s",
                index_path.exists(),
                meta_path.exists(),
            )
            return False

        try:
            with self._lock:
                new_index = faiss.read_index(str(index_path))
                with meta_path.open("rb") as f:
                    new_metadata = pickle.load(f)  # noqa: S301 - admin-owned file
                self._index = new_index
                self._metadata = new_metadata
                # Capture mtime so subsequent `available` checks can detect
                # a sibling worker's rebuild and reload automatically.
                try:
                    self._index_mtime = index_path.stat().st_mtime
                except OSError:
                    self._index_mtime = None
                from datetime import datetime, timezone

                self._loaded_at = datetime.now(timezone.utc).isoformat()
                logger.info(
                    "faiss_loaded chunks=%d mtime=%s",
                    self.chunk_count,
                    self._index_mtime,
                )
            return True
        except Exception:
            logger.exception("faiss_load_failed")
            return False

    # ── Retrieval ────────────────────────────────────────────────────────

    def embed(self, text: str) -> np.ndarray:
        return self.embed_batch([text])

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Dispatches to the configured embedding provider.
        Used by both the index builder and the per-query retrieval path."""
        provider = get_settings().embedding_provider
        if provider == "openai":
            return _embed_via_openai(texts)
        emb = self._get_embedder().encode(texts, convert_to_numpy=True, batch_size=32)
        return emb.astype("float32")

    def retrieve(self, query: str, k: int | None = None) -> list[Retrieved]:
        if not self.available:
            return []
        settings = get_settings()
        k = k or settings.rag_top_k
        embedding = self.embed_batch([query])
        assert self._index is not None and self._metadata is not None
        distances, indices = self._index.search(embedding, k)
        results: list[Retrieved] = []
        texts = self._metadata.get("texts", [])
        sources = self._metadata.get("sources", [])
        for idx, dist in zip(indices[0], distances[0], strict=False):
            if idx == -1 or idx >= len(texts):
                continue
            results.append(
                Retrieved(
                    text=str(texts[idx]),
                    source=str(sources[idx]) if idx < len(sources) else "unknown",
                    distance=float(dist),
                )
            )
        return results

    # ── Generation ───────────────────────────────────────────────────────

    def _build_messages(
        self,
        history: list[dict[str, str]],
        user_query: str,
        retrieved: list[Retrieved],
    ) -> list[dict[str, str]]:
        documents_block = (
            "\n\n".join(f"Source: {r.source}\n{r.text}" for r in retrieved)
            if retrieved
            else "(no documents retrieved — answer from general knowledge but say so)"
        )
        user_content = (
            "Context from TripSafe knowledge base:\n"
            f"{documents_block}\n\n"
            f"User question: {user_query}"
        )
        return [*history, {"role": "user", "content": user_content}]

    def generate_answer(
        self,
        *,
        model: str,
        system_prompt: str,
        history: list[dict[str, str]],
        user_query: str,
        retrieved: list[Retrieved],
    ) -> str:
        client = self._get_anthropic()
        messages = self._build_messages(history, user_query, retrieved)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )
        parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts).strip()

    def stream_answer(
        self,
        *,
        model: str,
        system_prompt: str,
        history: list[dict[str, str]],
        user_query: str,
        retrieved: list[Retrieved],
    ):
        """Generator yielding text deltas as Claude produces them.
        Runs synchronously inside a worker thread; the caller bridges to
        async via a queue (see api/v1/chat.py stream endpoint)."""
        client = self._get_anthropic()
        messages = self._build_messages(history, user_query, retrieved)
        with client.messages.stream(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text


engine = RagEngine()


# ── OpenAI embedding fallback ───────────────────────────────────────────

def _embed_via_openai(texts: list[str]) -> np.ndarray:
    """Embeddings only — never chat. Used when EMBEDDING_PROVIDER=openai.

    Goes through httpx (already a dep) so we don't pull in the openai SDK.
    Same corporate-proxy SSL bypass as the local provider is honored.
    """
    import os

    import httpx

    settings = get_settings()
    key = settings.openai_api_key.get_secret_value() or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is empty. Set it in .env."
        )

    verify_tls = (
        os.environ.get("EMBEDDING_DISABLE_SSL", "false").lower() != "true"
    )

    # OpenAI accepts up to 2048 inputs per call; chunk to be safe.
    batch_size = 96
    vectors: list[list[float]] = []
    with httpx.Client(timeout=60.0, verify=verify_tls) as client:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": settings.openai_embedding_model, "input": batch},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI embeddings failed: {resp.status_code} {resp.text[:300]}")
            data = resp.json()["data"]
            vectors.extend(d["embedding"] for d in data)
    return np.array(vectors, dtype="float32")
