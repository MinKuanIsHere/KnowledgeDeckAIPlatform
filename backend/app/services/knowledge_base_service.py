from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeBase, KnowledgeFile


async def create_knowledge_base(
    session: AsyncSession,
    *,
    owner_user_id: int,
    name: str,
    description: str | None,
) -> KnowledgeBase:
    kb = KnowledgeBase(
        owner_user_id=owner_user_id, name=name, description=description
    )
    session.add(kb)
    await session.flush()
    await session.commit()
    await session.refresh(kb)
    return kb


async def name_taken(session: AsyncSession, *, owner_user_id: int, name: str) -> bool:
    existing = await session.scalar(
        select(KnowledgeBase.id).where(
            KnowledgeBase.owner_user_id == owner_user_id,
            KnowledgeBase.name == name,
            KnowledgeBase.deleted_at.is_(None),
        )
    )
    return existing is not None


async def list_knowledge_bases(
    session: AsyncSession, *, owner_user_id: int
) -> list[tuple[KnowledgeBase, int]]:
    file_count = (
        select(
            KnowledgeFile.knowledge_base_id.label("kb_id"),
            func.count(KnowledgeFile.id).label("cnt"),
        )
        .where(KnowledgeFile.deleted_at.is_(None))
        .group_by(KnowledgeFile.knowledge_base_id)
        .subquery()
    )
    rows = await session.execute(
        select(KnowledgeBase, func.coalesce(file_count.c.cnt, 0))
        .outerjoin(file_count, file_count.c.kb_id == KnowledgeBase.id)
        .where(
            KnowledgeBase.owner_user_id == owner_user_id,
            KnowledgeBase.deleted_at.is_(None),
        )
        .order_by(KnowledgeBase.created_at.desc())
    )
    return [(kb, int(cnt)) for kb, cnt in rows.all()]


async def get_owned_kb(
    session: AsyncSession, *, owner_user_id: int, kb_id: int
) -> KnowledgeBase | None:
    return await session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_user_id == owner_user_id,
            KnowledgeBase.deleted_at.is_(None),
        )
    )


async def soft_delete_kb_cascade(
    session: AsyncSession, *, kb: KnowledgeBase
) -> None:
    now = datetime.now(timezone.utc)
    await session.execute(
        update(KnowledgeFile)
        .where(
            KnowledgeFile.knowledge_base_id == kb.id,
            KnowledgeFile.deleted_at.is_(None),
        )
        .values(deleted_at=now)
    )
    kb.deleted_at = now
    await session.commit()
