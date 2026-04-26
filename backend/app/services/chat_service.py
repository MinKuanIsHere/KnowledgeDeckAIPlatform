"""Chat orchestration: history → optional RAG retrieval → vLLM streaming.

Uses LangChain's ChatOpenAI for the streaming LLM call so we get token-level
async streaming for free, plus the standard message types. RAG retrieval calls
the existing EmbeddingClient + qdrant_store; assembling the final prompt is
done manually because there is no template substitution worth abstracting.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.db.models import ChatMessage, ChatRole
from app.services import ingestion, qdrant_store

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are KnowledgeDeck, a concise assistant. When context is provided, "
    "ground your answer in it and avoid speculation. If the context is empty "
    "or irrelevant, answer from general knowledge but say so."
)
RAG_TOP_K = 5
HISTORY_MAX_MESSAGES = 10


def _build_llm() -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(
        model=s.llm_model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        streaming=True,
        temperature=0.3,
    )


def _format_context(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return ""
    out: list[str] = []
    for i, hit in enumerate(hits, start=1):
        payload = hit["payload"]
        page = payload.get("page_number")
        loc = f" (p.{page})" if page else ""
        out.append(f"[{i}] {payload['filename']}{loc}\n{payload['text']}")
    return "\n\n".join(out)


def _history_to_messages(rows: list[ChatMessage]) -> list[HumanMessage | AIMessage]:
    msgs: list[HumanMessage | AIMessage] = []
    for r in rows[-HISTORY_MAX_MESSAGES:]:
        if r.role is ChatRole.USER:
            msgs.append(HumanMessage(content=r.content))
        else:
            msgs.append(AIMessage(content=r.content))
    return msgs


async def retrieve_context(
    *, user_id: int, kb_ids: list[int] | None, query: str
) -> tuple[str, list[dict[str, Any]]]:
    """Returns (context_block, citations). Citations are unique by file_id."""
    query_vec = await ingestion.embed_query(query)
    hits = await qdrant_store.search(
        query_vector=query_vec, user_id=user_id, kb_ids=kb_ids, top_k=RAG_TOP_K
    )
    context = _format_context(hits)
    seen: set[int] = set()
    citations: list[dict[str, Any]] = []
    for hit in hits:
        fid = hit["payload"]["file_id"]
        if fid in seen:
            continue
        seen.add(fid)
        citations.append({"file_id": fid, "filename": hit["payload"]["filename"]})
    return context, citations


async def stream_answer(
    *,
    history: list[ChatMessage],
    user_message: str,
    context: str,
) -> AsyncIterator[str]:
    """Yields LLM token chunks as plain strings."""
    messages: list[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(_history_to_messages(history))
    if context:
        messages.append(SystemMessage(content=f"Context:\n{context}"))
    messages.append(HumanMessage(content=user_message))

    llm = _build_llm()
    async for chunk in llm.astream(messages):
        if chunk.content:
            yield chunk.content
