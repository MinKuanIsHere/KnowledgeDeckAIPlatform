import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_migration_creates_users_table(db_session) -> None:
    result = await db_session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'users'
            ORDER BY column_name
            """
        )
    )
    columns = [row[0] for row in result.all()]
    assert columns == ["created_at", "id", "password", "username"]
