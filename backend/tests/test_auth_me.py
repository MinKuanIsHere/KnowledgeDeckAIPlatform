import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import User


@pytest.fixture()
async def seeded_user(db_session) -> User:
    user = User(username="alice", password="hunter2")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture()
async def http_client():
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_me_success(http_client, seeded_user: User) -> None:
    response = await http_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer u_{seeded_user.id}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == seeded_user.id
    assert body["username"] == "alice"
    assert "created_at" in body


@pytest.mark.asyncio
async def test_me_missing_header(http_client) -> None:
    response = await http_client.get("/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


@pytest.mark.asyncio
async def test_me_unknown_id(http_client) -> None:
    response = await http_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer u_999999"},
    )
    assert response.status_code == 401
