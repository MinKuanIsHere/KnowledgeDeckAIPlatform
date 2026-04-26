"""Mock slide-outline generation.

For the MVP we use the same LangChain ChatOpenAI client that powers the chat
endpoint to produce a plain-text outline. When Presenton lands, this module
becomes the orchestration layer: outline -> slide JSON -> Presenton API call
-> store the rendered PPTX in MinIO.
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.services import chat_service

logger = logging.getLogger(__name__)

OUTLINE_SYSTEM_PROMPT = (
    "You are a slide-deck planner. Given a user prompt and optional reference "
    "context, produce a concise outline suitable for a 5-10 slide deck. "
    "Format strictly as plain text:\n"
    "- A one-line deck title\n"
    "- For each slide: a numbered heading and 2-4 bullet points\n"
    "- A final 'Closing' slide\n"
    "Do not invent facts beyond the context. Keep bullets short."
)


def _build_llm() -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(
        model=s.llm_model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        streaming=False,
        temperature=0.3,
    )


async def generate_outline(
    *,
    user_id: int,
    prompt: str,
    use_rag: bool,
    kb_ids: list[int] | None,
) -> tuple[str, list[dict]]:
    """Returns (outline_text, citations). Citations is empty when use_rag=False."""
    context = ""
    citations: list[dict] = []
    if use_rag:
        context, citations = await chat_service.retrieve_context(
            user_id=user_id, kb_ids=kb_ids, query=prompt
        )

    messages: list = [SystemMessage(content=OUTLINE_SYSTEM_PROMPT)]
    if context:
        messages.append(SystemMessage(content=f"Reference context:\n{context}"))
    messages.append(HumanMessage(content=prompt))

    llm = _build_llm()
    response = await llm.ainvoke(messages)
    outline = (response.content or "").strip()
    if citations:
        # Append a "Sources" footer so the downloaded text shows attribution.
        names = ", ".join(dict.fromkeys(c["filename"] for c in citations))
        outline = f"{outline}\n\nSources: {names}"
    return outline, citations
