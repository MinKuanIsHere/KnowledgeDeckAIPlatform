import pytest
from fastapi import HTTPException

from app.shared.api.deps import get_current_user
from app.db.models import User


@pytest.fixture()
async def seeded_user(db_session) -> User:
    user = User(username="alice", password="hunter2")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_current_user_resolves_existing_user(db_session, seeded_user: User) -> None:
    user = await get_current_user(authorization=f"Bearer u_{seeded_user.id}", session=db_session)
    assert user.id == seeded_user.id


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_header(db_session) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization=None, session=db_session)
    assert exc.value.status_code == 401
    assert exc.value.detail == "invalid_token"


@pytest.mark.asyncio
async def test_get_current_user_rejects_wrong_scheme(db_session) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization="Basic abc", session=db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_malformed_token(db_session) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization="Bearer u_abc", session=db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_unknown_id(db_session) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization="Bearer u_999999", session=db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_id_zero(db_session) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization="Bearer u_0", session=db_session)
    assert exc.value.status_code == 401
    assert exc.value.detail == "invalid_token"


@pytest.mark.asyncio
async def test_get_current_user_rejects_oversized_id(db_session) -> None:
    # 25-digit id exceeds PostgreSQL BIGINT — must be rejected by the regex
    # rather than reaching the database (where it would surface as 500).
    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            authorization="Bearer u_99999999999999999999999999",
            session=db_session,
        )
    assert exc.value.status_code == 401
    assert exc.value.detail == "invalid_token"


@pytest.mark.asyncio
async def test_get_current_user_rejects_leading_zero(db_session, seeded_user: User) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            authorization=f"Bearer u_0{seeded_user.id}", session=db_session
        )
    assert exc.value.status_code == 401
