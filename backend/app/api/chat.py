"""Chat sessions + streaming endpoint.

GET/POST/DELETE /chat/sessions for session management; POST /chat/stream for
the actual SSE streaming response. Auth via the existing get_current_user
dependency. Sessions are user-scoped — cross-user access returns 404.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.base import async_session_factory, get_db
from app.db.models import ChatMessage, ChatRole, ChatSession, User
from app.services import chat_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SessionOut(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: list[dict[str, Any]] | None
    created_at: str


class SessionDetail(SessionOut):
    messages: list[MessageOut]


class StreamRequest(BaseModel):
    session_id: int
    message: str = Field(min_length=1)
    use_rag: bool = False
    kb_ids: list[int] | None = None


def _session_out(s: ChatSession) -> SessionOut:
    return SessionOut(
        id=s.id,
        title=s.title,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


def _message_out(m: ChatMessage) -> MessageOut:
    return MessageOut(
        id=m.id,
        role=m.role.value,
        content=m.content,
        citations=m.citations,
        created_at=m.created_at.isoformat(),
    )


async def _load_owned_session(
    session: AsyncSession, *, owner_user_id: int, session_id: int, with_messages: bool = False
) -> ChatSession:
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.owner_user_id == owner_user_id,
        ChatSession.deleted_at.is_(None),
    )
    if with_messages:
        stmt = stmt.options(selectinload(ChatSession.messages))
    s = await session.scalar(stmt)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session_not_found")
    return s


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SessionOut:
    s = ChatSession(owner_user_id=user.id, title=body.title or "New Chat")
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return _session_out(s)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[SessionOut]:
    rows = await session.scalars(
        select(ChatSession)
        .where(
            ChatSession.owner_user_id == user.id,
            ChatSession.deleted_at.is_(None),
        )
        .order_by(ChatSession.updated_at.desc())
    )
    return [_session_out(s) for s in rows.all()]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SessionDetail:
    s = await _load_owned_session(
        session, owner_user_id=user.id, session_id=session_id, with_messages=True
    )
    return SessionDetail(
        id=s.id,
        title=s.title,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
        messages=[_message_out(m) for m in s.messages],
    )


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: int,
    body: SessionUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SessionOut:
    s = await _load_owned_session(
        session, owner_user_id=user.id, session_id=session_id
    )
    s.title = body.title
    await session.commit()
    await session.refresh(s)
    return _session_out(s)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    s = await _load_owned_session(session, owner_user_id=user.id, session_id=session_id)
    s.deleted_at = datetime.now(timezone.utc)
    await session.commit()


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format a single Server-Sent Events frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def stream_chat(
    body: StreamRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    # Load session + history + persist user message in the request session so
    # the streaming generator (which opens its own session) sees them.
    s = await _load_owned_session(
        session, owner_user_id=user.id, session_id=body.session_id, with_messages=True
    )
    history = list(s.messages)
    user_msg = ChatMessage(
        session_id=s.id, role=ChatRole.USER, content=body.message, citations=None
    )
    session.add(user_msg)
    # Auto-title from first user message (within ~50 chars, single line).
    if not history:
        first_line = body.message.strip().splitlines()[0]
        s.title = (first_line[:50] + "...") if len(first_line) > 50 else first_line
    s.updated_at = datetime.now(timezone.utc)
    await session.commit()

    user_id = user.id
    session_id = s.id
    user_message = body.message
    use_rag = body.use_rag
    kb_ids = body.kb_ids

    async def generator() -> AsyncIterator[str]:
        try:
            citations: list[dict[str, Any]] = []
            context = ""
            if use_rag:
                context, citations = await chat_service.retrieve_context(
                    user_id=user_id, kb_ids=kb_ids, query=user_message
                )

            collected: list[str] = []
            async for token in chat_service.stream_answer(
                history=history, user_message=user_message, context=context
            ):
                collected.append(token)
                yield _sse("token", {"text": token})

            # Persist the assistant turn in a fresh session — request session
            # already returned to the pool when the response started streaming.
            factory = async_session_factory()
            async with factory() as save_session:
                save_session.add(
                    ChatMessage(
                        session_id=session_id,
                        role=ChatRole.ASSISTANT,
                        content="".join(collected),
                        citations=citations or None,
                    )
                )
                touched = await save_session.scalar(
                    select(ChatSession).where(ChatSession.id == session_id)
                )
                if touched is not None:
                    touched.updated_at = datetime.now(timezone.utc)
                await save_session.commit()

            yield _sse("citations", {"items": citations})
            yield _sse("done", {})
        except Exception as exc:  # pragma: no cover - prototype
            logger.exception("chat_stream_failed session=%s", session_id)
            yield _sse("error", {"message": str(exc)[:300]})

    return StreamingResponse(generator(), media_type="text/event-stream")
