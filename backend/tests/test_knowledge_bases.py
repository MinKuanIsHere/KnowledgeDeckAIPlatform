import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import User


@pytest.fixture()
async def alice(db_session) -> User:
    user = User(username="alice", password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture()
async def bob(db_session) -> User:
    user = User(username="bob", password="x")
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


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer u_{user.id}"}


@pytest.mark.asyncio
async def test_create_kb_returns_201_with_body(http_client, alice: User) -> None:
    res = await http_client.post(
        "/knowledge-bases",
        json={"name": "Notes", "description": "personal"},
        headers=auth(alice),
    )
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Notes"
    assert body["description"] == "personal"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_kb_requires_auth(http_client) -> None:
    res = await http_client.post("/knowledge-bases", json={"name": "Notes"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_kb_rejects_empty_name(http_client, alice: User) -> None:
    res = await http_client.post(
        "/knowledge-bases", json={"name": ""}, headers=auth(alice)
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_kb_duplicate_name_returns_409(http_client, alice: User) -> None:
    await http_client.post(
        "/knowledge-bases", json={"name": "Notes"}, headers=auth(alice)
    )
    res = await http_client.post(
        "/knowledge-bases", json={"name": "Notes"}, headers=auth(alice)
    )
    assert res.status_code == 409
    assert res.json() == {"detail": "duplicate_kb_name"}


@pytest.mark.asyncio
async def test_create_kb_same_name_for_different_users_ok(
    http_client, alice: User, bob: User
) -> None:
    r1 = await http_client.post(
        "/knowledge-bases", json={"name": "Notes"}, headers=auth(alice)
    )
    r2 = await http_client.post(
        "/knowledge-bases", json={"name": "Notes"}, headers=auth(bob)
    )
    assert r1.status_code == 201
    assert r2.status_code == 201


@pytest.mark.asyncio
async def test_list_kbs_returns_only_owners_kbs_with_zero_file_count(
    http_client, alice: User, bob: User
) -> None:
    await http_client.post(
        "/knowledge-bases", json={"name": "A1"}, headers=auth(alice)
    )
    await http_client.post(
        "/knowledge-bases", json={"name": "A2"}, headers=auth(alice)
    )
    await http_client.post(
        "/knowledge-bases", json={"name": "B1"}, headers=auth(bob)
    )
    res = await http_client.get("/knowledge-bases", headers=auth(alice))
    assert res.status_code == 200
    body = res.json()
    names = [kb["name"] for kb in body]
    assert set(names) == {"A1", "A2"}
    assert all(kb["file_count"] == 0 for kb in body)


@pytest.mark.asyncio
async def test_delete_kb_returns_204_and_removes_from_list(
    http_client, alice: User
) -> None:
    create = await http_client.post(
        "/knowledge-bases", json={"name": "X"}, headers=auth(alice)
    )
    kb_id = create.json()["id"]
    res = await http_client.delete(f"/knowledge-bases/{kb_id}", headers=auth(alice))
    assert res.status_code == 204
    listed = await http_client.get("/knowledge-bases", headers=auth(alice))
    assert listed.json() == []


@pytest.mark.asyncio
async def test_delete_other_users_kb_returns_404(
    http_client, alice: User, bob: User
) -> None:
    create = await http_client.post(
        "/knowledge-bases", json={"name": "X"}, headers=auth(alice)
    )
    kb_id = create.json()["id"]
    res = await http_client.delete(f"/knowledge-bases/{kb_id}", headers=auth(bob))
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_can_recreate_kb_with_same_name_after_soft_delete(
    http_client, alice: User
) -> None:
    create = await http_client.post(
        "/knowledge-bases", json={"name": "Notes"}, headers=auth(alice)
    )
    kb_id = create.json()["id"]
    await http_client.delete(f"/knowledge-bases/{kb_id}", headers=auth(alice))
    res = await http_client.post(
        "/knowledge-bases", json={"name": "Notes"}, headers=auth(alice)
    )
    assert res.status_code == 201
