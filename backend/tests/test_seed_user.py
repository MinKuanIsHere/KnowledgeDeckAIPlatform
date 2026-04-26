import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import User
from app.startup import seed_initial_user


@pytest.mark.asyncio
async def test_seed_creates_user_when_username_does_not_exist(db_session) -> None:
    settings = Settings(initial_user_username="seed-user", initial_user_password="seed-pwd")
    await seed_initial_user(db_session, settings=settings)
    await db_session.commit()
    user = await db_session.scalar(select(User).where(User.username == "seed-user"))
    assert user is not None
    assert user.password == "seed-pwd"


@pytest.mark.asyncio
async def test_seed_skips_when_username_already_exists(db_session) -> None:
    db_session.add(User(username="seed-user", password="original"))
    await db_session.commit()

    settings = Settings(initial_user_username="seed-user", initial_user_password="different")
    await seed_initial_user(db_session, settings=settings)
    await db_session.commit()

    rows = (await db_session.scalars(select(User).where(User.username == "seed-user"))).all()
    assert len(rows) == 1
    assert rows[0].password == "original"  # idempotent: not overwritten


@pytest.mark.asyncio
async def test_seed_no_op_when_username_unset(db_session) -> None:
    settings = Settings(initial_user_username="", initial_user_password="anything")
    await seed_initial_user(db_session, settings=settings)
    await db_session.commit()
    rows = (await db_session.scalars(select(User))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_seed_no_op_when_password_unset(db_session) -> None:
    settings = Settings(initial_user_username="alice", initial_user_password="")
    await seed_initial_user(db_session, settings=settings)
    await db_session.commit()
    rows = (await db_session.scalars(select(User))).all()
    assert rows == []
