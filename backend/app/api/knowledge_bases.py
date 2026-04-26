from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.db.models import User
from app.services import knowledge_base_service as svc

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class KnowledgeBaseOut(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: str


class KnowledgeBaseListItem(KnowledgeBaseOut):
    file_count: int


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
async def create_kb(
    body: KnowledgeBaseCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> KnowledgeBaseOut:
    if await svc.name_taken(session, owner_user_id=user.id, name=body.name):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="duplicate_kb_name")
    kb = await svc.create_knowledge_base(
        session,
        owner_user_id=user.id,
        name=body.name,
        description=body.description,
    )
    return KnowledgeBaseOut(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        created_at=kb.created_at.isoformat(),
    )


@router.get("", response_model=list[KnowledgeBaseListItem])
async def list_kbs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[KnowledgeBaseListItem]:
    items = await svc.list_knowledge_bases(session, owner_user_id=user.id)
    return [
        KnowledgeBaseListItem(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            created_at=kb.created_at.isoformat(),
            file_count=cnt,
        )
        for kb, cnt in items
    ]


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb(
    kb_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    kb = await svc.get_owned_kb(session, owner_user_id=user.id, kb_id=kb_id)
    if kb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="kb_not_found")
    await svc.soft_delete_kb_cascade(session, kb=kb)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
