from app.db.models import User


def test_user_table_metadata() -> None:
    assert User.__tablename__ == "users"
    columns = {c.name for c in User.__table__.columns}
    assert columns == {"id", "username", "password", "created_at"}
