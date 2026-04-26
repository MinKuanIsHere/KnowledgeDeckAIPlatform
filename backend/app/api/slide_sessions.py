"""Slide-planner sessions: conversational outline + Presenton render.

Mirrors the chat session API but replaces the chat system prompt with a
slide-planner one (in slide_chat_service) and adds a /render endpoint that
calls Presenton, retrieves the PPTX from the shared volume, and stores it
in MinIO.
"""
from __future__ import annotations

import io
import json
import logging
import re
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
from app.db.models import SlideMessage, SlideRole, SlideSession, SlideStatus, User
from app.services import slide_chat_service
from app.services.object_storage import get_minio_client
from app.services.presenton_client import PresentonError, get_presenton_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/slide-sessions", tags=["slide-sessions"])

# Pulled from slide_chat_service for centralized parsing.
_OUTLINE_READY_MARKER = slide_chat_service.OUTLINE_READY_MARKER
# Matches any "## Slide N: Title" block until the next "## Slide" or end.
_SLIDE_BLOCK_RE = re.compile(
    r"^##\s*Slide\s+\d+\s*:.*?(?=^##\s*Slide\s+\d+\s*:|\Z)",
    re.DOTALL | re.MULTILINE,
)


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SessionOut(BaseModel):
    id: int
    title: str
    status: str
    has_pptx: bool
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
    message: str = Field(min_length=1)
    use_rag: bool = False
    kb_ids: list[int] | None = None


class RenderRequest(BaseModel):
    template: str = Field(default="general", max_length=64)
    language: str = Field(default="English", max_length=64)


def _session_out(s: SlideSession) -> SessionOut:
    return SessionOut(
        id=s.id,
        title=s.title,
        status=s.status.value,
        has_pptx=s.generated_pptx_key is not None,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


def _message_out(m: SlideMessage) -> MessageOut:
    return MessageOut(
        id=m.id,
        role=m.role.value,
        content=m.content,
        citations=m.citations,
        created_at=m.created_at.isoformat(),
    )


async def _load_owned_session(
    session: AsyncSession,
    *,
    owner_user_id: int,
    session_id: int,
    with_messages: bool = False,
) -> SlideSession:
    stmt = select(SlideSession).where(
        SlideSession.id == session_id,
        SlideSession.owner_user_id == owner_user_id,
        SlideSession.deleted_at.is_(None),
    )
    if with_messages:
        stmt = stmt.options(selectinload(SlideSession.messages))
    s = await session.scalar(stmt)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session_not_found")
    return s


def _split_slide_blocks(outline_markdown: str) -> list[str]:
    """Splits an outline like:
        ## Slide 1: Intro\n- foo\n\n## Slide 2: Body\n- bar
    into per-slide markdown strings."""
    blocks = [m.group(0).strip() for m in _SLIDE_BLOCK_RE.finditer(outline_markdown)]
    return [b for b in blocks if b]


def _extract_outline(messages: list[SlideMessage]) -> str | None:
    """Returns the outline markdown from the most recent assistant message
    that emitted [OUTLINE_READY], with the marker stripped. Returns None if
    no such message exists."""
    for m in reversed(messages):
        if m.role is not SlideRole.ASSISTANT:
            continue
        if _OUTLINE_READY_MARKER not in m.content:
            continue
        return m.content.replace(_OUTLINE_READY_MARKER, "").strip()
    return None


# --- Sessions CRUD ---


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SessionOut:
    s = SlideSession(owner_user_id=user.id, title=body.title or "New deck")
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return _session_out(s)


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[SessionOut]:
    rows = await session.scalars(
        select(SlideSession)
        .where(
            SlideSession.owner_user_id == user.id,
            SlideSession.deleted_at.is_(None),
        )
        .order_by(SlideSession.updated_at.desc())
    )
    return [_session_out(s) for s in rows.all()]


@router.get("/{session_id}", response_model=SessionDetail)
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
        status=s.status.value,
        has_pptx=s.generated_pptx_key is not None,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
        messages=[_message_out(m) for m in s.messages],
    )


@router.patch("/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: int,
    body: SessionUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SessionOut:
    s = await _load_owned_session(session, owner_user_id=user.id, session_id=session_id)
    s.title = body.title
    await session.commit()
    await session.refresh(s)
    return _session_out(s)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    s = await _load_owned_session(session, owner_user_id=user.id, session_id=session_id)
    s.deleted_at = datetime.now(timezone.utc)
    await session.commit()


# --- Streaming chat ---


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{session_id}/stream")
async def stream_session(
    session_id: int,
    body: StreamRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    s = await _load_owned_session(
        session, owner_user_id=user.id, session_id=session_id, with_messages=True
    )
    history = list(s.messages)

    user_msg = SlideMessage(
        session_id=s.id, role=SlideRole.USER, content=body.message, citations=None
    )
    session.add(user_msg)
    if not history:
        # Auto-title from first user message.
        first_line = body.message.strip().splitlines()[0]
        s.title = (first_line[:50] + "...") if len(first_line) > 50 else first_line
    s.updated_at = datetime.now(timezone.utc)
    await session.commit()

    user_id = user.id
    sid = s.id
    user_message = body.message
    use_rag = body.use_rag
    kb_ids = body.kb_ids

    async def generator() -> AsyncIterator[str]:
        try:
            token_stream, citations = await slide_chat_service.stream_planner(
                history=history,
                user_message=user_message,
                user_id=user_id,
                use_rag=use_rag,
                kb_ids=kb_ids,
            )
            collected: list[str] = []
            async for token in token_stream:
                collected.append(token)
                yield _sse("token", {"text": token})

            content = "".join(collected)
            outline_ready = _OUTLINE_READY_MARKER in content

            factory = async_session_factory()
            async with factory() as save_session:
                save_session.add(
                    SlideMessage(
                        session_id=sid,
                        role=SlideRole.ASSISTANT,
                        content=content,
                        citations=citations or None,
                    )
                )
                touched = await save_session.scalar(
                    select(SlideSession).where(SlideSession.id == sid)
                )
                if touched is not None:
                    touched.updated_at = datetime.now(timezone.utc)
                await save_session.commit()

            yield _sse("citations", {"items": citations})
            yield _sse("done", {"outline_ready": outline_ready})
        except Exception as exc:  # pragma: no cover - prototype
            logger.exception("slide_stream_failed session=%s", sid)
            yield _sse("error", {"message": str(exc)[:300]})

    return StreamingResponse(generator(), media_type="text/event-stream")


# --- Render via Presenton ---


@router.post("/{session_id}/render", response_model=SessionOut)
async def render_session(
    session_id: int,
    body: RenderRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SessionOut:
    s = await _load_owned_session(
        session, owner_user_id=user.id, session_id=session_id, with_messages=True
    )
    outline_md = _extract_outline(list(s.messages))
    if outline_md is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="no_outline_ready",
        )
    slide_blocks = _split_slide_blocks(outline_md)
    if not slide_blocks:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="outline_unparsable",
        )

    s.status = SlideStatus.RENDERING
    s.updated_at = datetime.now(timezone.utc)
    await session.commit()

    presenton = get_presenton_client()
    try:
        result = await presenton.generate(
            slides_markdown=slide_blocks,
            n_slides=len(slide_blocks),
            language=body.language,
            template=body.template,
            export_as="pptx",
        )
        path = result.get("path")
        if not path:
            raise PresentonError("presenton response missing 'path'")
        pptx_bytes = presenton.read_artifact(path)
    except Exception as exc:
        logger.exception("presenton_render_failed session=%s", session_id)
        s.status = SlideStatus.FAILED
        await session.commit()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"presenton_failed: {exc}"
        )

    # Persist the PPTX in MinIO under a stable key per session. New renders
    # overwrite, matching the file upload key layout.
    minio = get_minio_client()
    key = f"slide-sessions/{session_id}/latest.pptx"
    await minio.put_object(
        key,
        io.BytesIO(pptx_bytes),
        len(pptx_bytes),
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )

    s.status = SlideStatus.RENDERED
    s.generated_pptx_key = key
    s.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(s)
    return _session_out(s)


@router.get("/{session_id}/download")
async def download_session(
    session_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    s = await _load_owned_session(
        session, owner_user_id=user.id, session_id=session_id
    )
    if s.generated_pptx_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_rendered_yet")

    minio = get_minio_client()
    # minio-py exposes a streaming get; fetch the bytes via the underlying
    # client. Wrapping with asyncio.to_thread for symmetry.
    import asyncio

    def _fetch() -> bytes:
        response = minio._client.get_object(minio.bucket, s.generated_pptx_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    pptx_bytes = await asyncio.to_thread(_fetch)
    safe_title = s.title.replace('"', "'").strip() or f"deck-{s.id}"
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_title}.pptx"',
    }
    return StreamingResponse(
        io.BytesIO(pptx_bytes),
        media_type=(
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ),
        headers=headers,
    )
