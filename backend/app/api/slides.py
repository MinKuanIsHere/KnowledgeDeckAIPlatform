"""Slide projects: mock outline generation, list, download, delete."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.db.models import SlideProject, User
from app.services import slide_service

router = APIRouter(prefix="/slides", tags=["slides"])


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    title: str | None = Field(default=None, max_length=200)
    use_rag: bool = False
    kb_ids: list[int] | None = None


class SlideProjectOut(BaseModel):
    id: int
    title: str
    prompt: str
    use_rag: bool
    kb_ids: list[int] | None
    created_at: str


def _project_out(p: SlideProject) -> SlideProjectOut:
    return SlideProjectOut(
        id=p.id,
        title=p.title,
        prompt=p.prompt,
        use_rag=p.use_rag,
        kb_ids=p.kb_ids,
        created_at=p.created_at.isoformat(),
    )


def _auto_title(prompt: str) -> str:
    first_line = prompt.strip().splitlines()[0]
    return (first_line[:50] + "...") if len(first_line) > 50 else first_line


async def _load_owned_project(
    session: AsyncSession, *, owner_user_id: int, project_id: int
) -> SlideProject:
    p = await session.scalar(
        select(SlideProject).where(
            SlideProject.id == project_id,
            SlideProject.owner_user_id == owner_user_id,
            SlideProject.deleted_at.is_(None),
        )
    )
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="project_not_found")
    return p


@router.post("/generate", response_model=SlideProjectOut, status_code=status.HTTP_201_CREATED)
async def generate(
    body: GenerateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SlideProjectOut:
    outline, _citations = await slide_service.generate_outline(
        user_id=user.id,
        prompt=body.prompt,
        use_rag=body.use_rag,
        kb_ids=body.kb_ids,
    )
    project = SlideProject(
        owner_user_id=user.id,
        title=body.title or _auto_title(body.prompt),
        prompt=body.prompt,
        use_rag=body.use_rag,
        kb_ids=body.kb_ids,
        outline=outline,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return _project_out(project)


@router.get("/projects", response_model=list[SlideProjectOut])
async def list_projects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[SlideProjectOut]:
    rows = await session.scalars(
        select(SlideProject)
        .where(
            SlideProject.owner_user_id == user.id,
            SlideProject.deleted_at.is_(None),
        )
        .order_by(SlideProject.created_at.desc())
    )
    return [_project_out(p) for p in rows.all()]


@router.get("/projects/{project_id}/download")
async def download_project(
    project_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    project = await _load_owned_project(
        session, owner_user_id=user.id, project_id=project_id
    )
    body = project.outline.encode("utf-8")
    # Mock phase: served as text/plain. Frontend labels this as an outline
    # preview. When Presenton lands, swap to application/vnd.openxmlformats-
    # officedocument.presentationml.presentation + .pptx filename.
    safe_title = project.title.replace('"', "'").strip() or f"slides-{project.id}"
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_title}.txt"',
    }
    return StreamingResponse(BytesIO(body), media_type="text/plain", headers=headers)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    project = await _load_owned_project(
        session, owner_user_id=user.id, project_id=project_id
    )
    project.deleted_at = datetime.now(timezone.utc)
    await session.commit()
