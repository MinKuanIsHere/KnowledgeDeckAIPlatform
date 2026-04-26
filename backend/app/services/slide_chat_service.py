"""Slide-planner conversational service.

Mirrors chat_service but with a different system prompt. The LLM is
instructed to ask clarifying questions, propose markdown outlines, and
mark its turn with `[OUTLINE_READY]` once the user has confirmed.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.db.models import SlideMessage, SlideRole
from app.services import chat_service

logger = logging.getLogger(__name__)

OUTLINE_READY_MARKER = "[OUTLINE_READY]"

SYSTEM_PROMPT = (
    "You are KnowledgeDeck Slide Planner — a focused assistant whose only "
    "job is to help the user produce a slide deck.\n\n"
    "Workflow:\n"
    "1. If the user has not yet specified them, ask clarifying questions about: "
    "target audience, total number of slides (3-15), language for the deck, "
    "tone (professional / casual / educational / sales / etc.), VISUAL "
    "TEMPLATE preference, and any specific topics that must be covered or "
    "avoided. Ask only the questions that are still missing — do not re-ask "
    "things already in scope.\n"
    "   Visual templates available in Presenton:\n"
    "     - `general` — clean, neutral default\n"
    "     - `modern` — bold, contemporary styling\n"
    "   Use ONLY one of these two values. If the user requests anything "
    "else (e.g. classic / professional), pick whichever of the two fits "
    "their intent better and tell them which one you chose. If unstated, "
    "default to `general`.\n"
    "2. When you have enough information, propose a draft outline. Format "
    "STRICTLY as markdown with this exact structure:\n\n"
    "## Slide 1: <Title>\n"
    "- <bullet>\n"
    "- <bullet>\n\n"
    "## Slide 2: <Title>\n"
    "- <bullet>\n\n"
    "(...etc, one ## block per slide)\n\n"
    "3. Ask the user to review the outline and tell you what to adjust. "
    "Iterate until they are satisfied.\n"
    "4. Once the user confirms (\"yes\", \"go ahead\", \"render it\", or "
    "similar), produce the FINAL version of the outline in your reply, then "
    "end the message with a marker line that includes the chosen template "
    "and language as key=value args, on its own line. Examples:\n"
    "   `" + OUTLINE_READY_MARKER[:-1] + " template=modern]`\n"
    "   `" + OUTLINE_READY_MARKER[:-1] + " template=professional language=Spanish]`\n"
    "   `" + OUTLINE_READY_MARKER + "`  (= template=general language=English)\n"
    "Do not emit this marker until the user has explicitly confirmed they "
    "want to render.\n\n"
    "Rules:\n"
    "- Use the provided RAG context only to ground content; do not invent "
    "facts beyond what is given.\n"
    "- Keep bullets concise (one short sentence each).\n"
    "- Do not write any prose between slide blocks in the outline itself; "
    "everything outside the ## blocks belongs above or below the outline.\n"
    "- Never emit the OUTLINE_READY marker on a turn where you are still "
    "asking questions or revising the outline."
)
HISTORY_MAX_MESSAGES = 12


def _build_llm() -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(
        model=s.llm_model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        streaming=True,
        temperature=0.3,
    )


def _history_to_messages(rows: list[SlideMessage]) -> list[HumanMessage | AIMessage]:
    msgs: list[HumanMessage | AIMessage] = []
    for r in rows[-HISTORY_MAX_MESSAGES:]:
        if r.role is SlideRole.USER:
            msgs.append(HumanMessage(content=r.content))
        else:
            msgs.append(AIMessage(content=r.content))
    return msgs


async def stream_planner(
    *,
    history: list[SlideMessage],
    user_message: str,
    user_id: int,
    use_rag: bool,
    kb_ids: list[int] | None,
) -> tuple[AsyncIterator[str], list[dict[str, Any]]]:
    """Returns the token iterator plus citations gathered for this turn.

    Two-phase: do RAG retrieval up front (so the citations list is known
    before streaming starts), then return an iterator the caller can drain.

    For slide-maker we anchor the retrieval query to the FIRST user message
    of the session — that's the deck's topic. Each later turn (clarifying
    answers, "yes render it", iteration tweaks) would otherwise re-embed and
    drag the retrieved chunks off-topic. Chat sessions keep the per-turn
    behavior because chat is exploratory.
    """
    context = ""
    citations: list[dict[str, Any]] = []
    if use_rag:
        first_user = next(
            (m.content for m in history if m.role is SlideRole.USER),
            user_message,
        )
        context, citations = await chat_service.retrieve_context(
            user_id=user_id, kb_ids=kb_ids, query=first_user
        )

    messages: list[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(_history_to_messages(history))
    if context:
        messages.append(SystemMessage(content=f"Reference context:\n{context}"))
    messages.append(HumanMessage(content=user_message))

    llm = _build_llm()

    async def gen() -> AsyncIterator[str]:
        async for chunk in llm.astream(messages):
            if chunk.content:
                yield chunk.content

    return gen(), citations
