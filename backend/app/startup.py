import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.base import async_session_factory
from app.db.models import User

logger = logging.getLogger(__name__)


async def seed_initial_user(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
) -> None:
    cfg = settings or get_settings()
    if not cfg.initial_user_username or not cfg.initial_user_password:
        return
    existing = await session.scalar(select(User).where(User.username == cfg.initial_user_username))
    if existing is not None:
        logger.info("seed_skipped existing_user=%s", cfg.initial_user_username)
        return
    session.add(User(username=cfg.initial_user_username, password=cfg.initial_user_password))
    await session.flush()
    logger.info("seed_created user=%s", cfg.initial_user_username)


@asynccontextmanager
async def lifespan(app: FastAPI):
    factory = async_session_factory()
    async with factory() as session:
        await seed_initial_user(session)
        await session.commit()

    from app.services.object_storage import get_minio_client
    await get_minio_client().ensure_bucket()

    yield
