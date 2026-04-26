"""Sparse embeddings via fastembed's `Qdrant/bm25`.

Why BM25 here: it's corpus-free (uses pre-computed IDF tables shipped
with the model), tiny (no neural weights, just a tokenizer + stats), and
complements dense bge-m3 well — sparse catches keyword/proper-noun
matches where dense embeddings hedge ("Kubernetes pod lifecycle" vs
"component lifecycle"), while dense catches paraphrase.

The model loads once on first use and is reused (fastembed caches the
worker in-process). All work runs through asyncio.to_thread because
fastembed is synchronous.
"""
from __future__ import annotations

import asyncio
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from fastembed import SparseTextEmbedding


@dataclass(frozen=True)
class SparseVec:
    indices: list[int]
    values: list[float]


_BM25_MODEL_NAME = "Qdrant/bm25"
_model: SparseTextEmbedding | None = None
_model_lock = threading.Lock()


def _get_model() -> SparseTextEmbedding:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SparseTextEmbedding(model_name=_BM25_MODEL_NAME)
    return _model


def _to_sparse_vec(raw: Any) -> SparseVec:
    """fastembed returns a SparseEmbedding-ish object with .indices / .values
    that are numpy arrays. Coerce to plain Python lists for Qdrant /
    JSON friendliness."""
    indices = [int(i) for i in raw.indices.tolist()]
    values = [float(v) for v in raw.values.tolist()]
    return SparseVec(indices=indices, values=values)


async def embed_passages(texts: Sequence[str]) -> list[SparseVec]:
    """Used at ingestion time. Pass the exact chunk text we'll store."""
    if not texts:
        return []

    def _impl() -> list[SparseVec]:
        model = _get_model()
        return [_to_sparse_vec(v) for v in model.embed(list(texts))]

    return await asyncio.to_thread(_impl)


async def embed_query(text: str) -> SparseVec:
    """Used at retrieval time. fastembed's BM25 uses the same vectorizer
    for query and passages, so we just re-use embed()."""

    def _impl() -> SparseVec:
        model = _get_model()
        # `query_embed` exists on neural sparse models (SPLADE) but BM25 in
        # fastembed handles either via .embed().
        result = list(model.embed([text]))
        return _to_sparse_vec(result[0])

    return await asyncio.to_thread(_impl)
