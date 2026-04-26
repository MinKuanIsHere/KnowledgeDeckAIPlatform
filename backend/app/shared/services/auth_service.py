from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def authenticate(session: AsyncSession, username: str, password: str) -> User | None:
    user = await session.scalar(select(User).where(User.username == username))
    if user is None:
        return None
    if user.password != password:
        return None
    return user
