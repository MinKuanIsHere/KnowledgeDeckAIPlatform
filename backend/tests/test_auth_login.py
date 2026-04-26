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
async def test_login_success(http_client, seeded_user: User) -> None:
    response = await http_client.post(
        "/auth/login",
        json={"username": "alice", "password": "hunter2"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token"] == f"u_{seeded_user.id}"
    assert body["user"] == {"id": seeded_user.id, "username": "alice"}


@pytest.mark.asyncio
async def test_login_wrong_password(http_client, seeded_user: User) -> None:
    response = await http_client.post(
        "/auth/login",
        json={"username": "alice", "password": "WRONG"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_credentials"}


@pytest.mark.asyncio
async def test_login_unknown_username(http_client) -> None:
    response = await http_client.post(
        "/auth/login",
        json={"username": "ghost", "password": "anything"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_credentials"}


@pytest.mark.asyncio
async def test_login_validation_error(http_client) -> None:
    response = await http_client.post("/auth/login", json={"username": "alice"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_empty_strings_return_422(http_client) -> None:
    response = await http_client.post(
        "/auth/login", json={"username": "", "password": ""}
    )
    assert response.status_code == 422
