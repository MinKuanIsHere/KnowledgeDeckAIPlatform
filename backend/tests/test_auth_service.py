import pytest

from app.db.models import User
from app.services.auth_service import authenticate


@pytest.fixture()
async def seeded_user(db_session) -> User:
    user = User(username="alice", password="hunter2")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_authenticate_success(db_session, seeded_user: User) -> None:
    user = await authenticate(db_session, "alice", "hunter2")
    assert user is not None
    assert user.id == seeded_user.id


@pytest.mark.asyncio
async def test_authenticate_wrong_password(db_session, seeded_user: User) -> None:
    assert await authenticate(db_session, "alice", "WRONG") is None


@pytest.mark.asyncio
async def test_authenticate_unknown_username(db_session) -> None:
    assert await authenticate(db_session, "ghost", "anything") is None


@pytest.mark.asyncio
async def test_authenticate_is_case_sensitive(db_session, seeded_user: User) -> None:
    assert await authenticate(db_session, "Alice", "hunter2") is None
