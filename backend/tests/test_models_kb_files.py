import pytest
from sqlalchemy import inspect, text

from app.db.models import FileStatus, KnowledgeBase, KnowledgeFile, User


@pytest.mark.asyncio
async def test_kb_file_tables_exist(db_session) -> None:
    def list_tables(conn) -> list[str]:
        return inspect(conn).get_table_names()

    tables = await db_session.run_sync(lambda s: list_tables(s.connection()))
    assert "knowledge_bases" in tables
    assert "files" in tables


@pytest.mark.asyncio
async def test_file_status_enum_has_all_values(db_session) -> None:
    rows = await db_session.execute(
        text("SELECT unnest(enum_range(NULL::file_status))::text AS v ORDER BY v")
    )
    values = {r[0] for r in rows.all()}
    assert values == {"uploaded", "parsing", "parsed", "embedding", "indexed", "failed"}


@pytest.mark.asyncio
async def test_can_create_kb_and_file(db_session) -> None:
    user = User(username="alice", password="x")
    db_session.add(user)
    await db_session.flush()
    kb = KnowledgeBase(owner_user_id=user.id, name="Notes", description="d")
    db_session.add(kb)
    await db_session.flush()
    f = KnowledgeFile(
        knowledge_base_id=kb.id,
        owner_user_id=user.id,
        filename="a.txt",
        extension="txt",
        size_bytes=10,
        content_sha256="abc",
        storage_key=f"kb/{kb.id}/files/0/original.txt",
        status=FileStatus.UPLOADED,
    )
    db_session.add(f)
    await db_session.commit()
    assert f.id is not None
    assert f.deleted_at is None
    assert f.status is FileStatus.UPLOADED


@pytest.mark.asyncio
async def test_kb_unique_partial_index(db_session) -> None:
    from sqlalchemy.exc import IntegrityError

    user = User(username="bob", password="x")
    db_session.add(user)
    await db_session.flush()
    db_session.add(KnowledgeBase(owner_user_id=user.id, name="Same"))
    await db_session.commit()
    db_session.add(KnowledgeBase(owner_user_id=user.id, name="Same"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
