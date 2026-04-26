"""Thin async-friendly wrapper around qdrant-client.

Single collection (`qdrant_collection`) for the whole app. Per-user / per-KB
isolation is enforced via payload filters at query time, not via separate
collections.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.core.config import get_settings


_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = QdrantClient(url=s.qdrant_url)
    return _client


async def ensure_collection() -> None:
    s = get_settings()

    def _impl() -> None:
        client = _get_client()
        if client.collection_exists(s.qdrant_collection):
            return
        client.create_collection(
            collection_name=s.qdrant_collection,
            vectors_config=qm.VectorParams(
                size=s.embedding_dim, distance=qm.Distance.COSINE
            ),
        )
        # Indexes used in retrieval filters. Cheap, idempotent on re-create.
        for field in ("user_id", "kb_id", "file_id"):
            client.create_payload_index(
                collection_name=s.qdrant_collection,
                field_name=field,
                field_schema=qm.PayloadSchemaType.INTEGER,
            )

    await asyncio.to_thread(_impl)


async def upsert_chunks(
    *,
    user_id: int,
    kb_id: int,
    file_id: int,
    filename: str,
    chunks: list[dict[str, Any]],
    vectors: list[list[float]],
) -> None:
    """`chunks` is a list of {text, page_number?, chunk_index} dicts."""
    s = get_settings()

    def _impl() -> None:
        points = [
            qm.PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={
                    "user_id": user_id,
                    "kb_id": kb_id,
                    "file_id": file_id,
                    "filename": filename,
                    "text": chunk["text"],
                    "page_number": chunk.get("page_number"),
                    "chunk_index": chunk["chunk_index"],
                },
            )
            for chunk, vec in zip(chunks, vectors, strict=True)
        ]
        _get_client().upsert(collection_name=s.qdrant_collection, points=points)

    await asyncio.to_thread(_impl)


async def delete_by_file(*, file_id: int) -> None:
    s = get_settings()

    def _impl() -> None:
        _get_client().delete(
            collection_name=s.qdrant_collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[qm.FieldCondition(key="file_id", match=qm.MatchValue(value=file_id))]
                )
            ),
        )

    await asyncio.to_thread(_impl)


async def search(
    *,
    query_vector: list[float],
    user_id: int,
    kb_ids: list[int] | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Returns a list of {score, payload} dicts."""
    s = get_settings()

    def _impl() -> list[dict[str, Any]]:
        must: list[qm.FieldCondition] = [
            qm.FieldCondition(key="user_id", match=qm.MatchValue(value=user_id))
        ]
        if kb_ids:
            must.append(
                qm.FieldCondition(key="kb_id", match=qm.MatchAny(any=kb_ids))
            )
        # qdrant-client 1.12+ deprecated `search()` in favor of `query_points`
        # which returns a `QueryResponse` with `.points`.
        response = _get_client().query_points(
            collection_name=s.qdrant_collection,
            query=query_vector,
            query_filter=qm.Filter(must=must),
            limit=top_k,
            with_payload=True,
        )
        return [{"score": p.score, "payload": p.payload} for p in response.points]

    return await asyncio.to_thread(_impl)
