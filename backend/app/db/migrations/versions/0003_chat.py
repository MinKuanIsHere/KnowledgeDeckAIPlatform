"""chat_sessions + chat_messages tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-26 11:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    chat_role = sa.Enum("user", "assistant", name="chat_role")
    chat_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.Text,
            nullable=False,
            server_default=sa.text("'New Chat'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_chat_sessions_owner_active",
        "chat_sessions",
        ["owner_user_id", "updated_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "session_id",
            sa.BigInteger,
            sa.ForeignKey("chat_sessions.id"),
            nullable=False,
        ),
        sa.Column(
            "role",
            # PG_ENUM required: sa.Enum silently drops create_type=False in
            # SQLAlchemy 2.0.x, causing DuplicateObject on the already-created
            # type (see 0002_kb_files.py for the same workaround).
            PG_ENUM("user", "assistant", name="chat_role", create_type=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_chat_messages_session_id",
        "chat_messages",
        ["session_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_owner_active", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    sa.Enum(name="chat_role").drop(op.get_bind(), checkfirst=True)
