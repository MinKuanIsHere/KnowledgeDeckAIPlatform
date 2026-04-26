"""Chat-only orchestration: history + (optional) RAG context → vLLM streaming.

RAG retrieval lives in `app.services.rag` and is shared with the slide
maker. This module contains:
  - the chat SYSTEM_PROMPT
  - `rewrite_for_retrieval` — chat-specific follow-up rewriter, used so
    multi-turn pronouns ("and Python?", "what about that one?") embed
    against a self-contained query rather than the literal user message
  - `stream_answer` — token-streaming reply assembly
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.db.models import ChatMessage, ChatRole

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are KnowledgeDeck, a helpful conversational assistant.\n\n"
    "This is a multi-turn conversation. The messages above (if any) are the "
    "prior turns — treat them as the running context. Refer back to facts, "
    "preferences, and details the user has shared earlier in the conversation, "
    "and maintain continuity across turns.\n\n"
    "When a `Context:` section is included by the system, prefer it as the "
    "source for factual claims about the user's documents. When `Context:` is "
    "absent or irrelevant to the question, answer from your general knowledge.\n\n"
    "Be concise. Do not refuse to recall information the user has shared "
    "earlier in this conversation — the conversation history above is yours "
    "to use."
)
# 20 = up to ~10 user/assistant pairs. Conversational chat tends to have
# short turns, so this is plenty before older turns fall off the window.
HISTORY_MAX_MESSAGES = 20


_REWRITE_SYSTEM = (
    "You rewrite chat questions into standalone search queries.\n"
    "Input: a short conversation history followed by the user's most recent "
    "question. The recent question may use pronouns ('that', 'it', 'this one'), "
    "elliptical references ('and Python?'), or implicit context that only "
    "makes sense relative to the prior turns.\n"
    "Output: a single self-contained query suitable for a vector search "
    "engine. Resolve all references inline. Do not add quotation marks. Do "
    "not explain. Do not prefix with 'Query:'. Output ONE LINE only.\n"
    "If the recent question is already standalone, output it unchanged."
)


async def rewrite_for_retrieval(
    history: list[ChatMessage], user_message: str
) -> str:
    """Returns a standalone query string, suitable for embedding.

    No-op (returns user_message verbatim) when history is empty — first
    turns are already standalone. On any LLM error, also falls back to
    user_message so retrieval still works.
    """
    if not history:
        return user_message
    # Compress to last few turns for the rewriter's context — full history
    # is overkill and slow.
    recent = history[-6:]
    transcript_lines: list[str] = []
    for m in recent:
        role = "User" if m.role is ChatRole.USER else "Assistant"
        # Trim long assistant responses; only the gist matters for reference
        # resolution.
        body = m.content if len(m.content) <= 400 else m.content[:400] + "..."
        transcript_lines.append(f"{role}: {body}")
    prompt = (
        "Conversation history:\n"
        + "\n".join(transcript_lines)
        + f"\n\nMost recent question:\n{user_message}\n\nStandalone query:"
    )

    s = get_settings()
    try:
        rewriter = ChatOpenAI(
            model=s.llm_model,
            base_url=s.llm_base_url,
            api_key=s.llm_api_key,
            streaming=False,
            temperature=0,
            max_tokens=128,
        )
        result = await rewriter.ainvoke(
            [SystemMessage(content=_REWRITE_SYSTEM), HumanMessage(content=prompt)]
        )
        rewritten = (result.content or "").strip()
        # Defensive: bail if model went off the rails (returned nothing,
        # multiline explanation, or something far longer than expected).
        if not rewritten or len(rewritten) > 500 or "\n" in rewritten:
            return user_message
        return rewritten
    except Exception:
        logger.exception("query_rewrite_failed; falling back to raw user message")
        return user_message


def _build_llm() -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(
        model=s.llm_model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        streaming=True,
        temperature=0.3,
    )


def _history_to_messages(rows: list[ChatMessage]) -> list[HumanMessage | AIMessage]:
    msgs: list[HumanMessage | AIMessage] = []
    for r in rows[-HISTORY_MAX_MESSAGES:]:
        if r.role is ChatRole.USER:
            msgs.append(HumanMessage(content=r.content))
        else:
            msgs.append(AIMessage(content=r.content))
    return msgs


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
