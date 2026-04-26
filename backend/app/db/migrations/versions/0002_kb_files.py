"""knowledge_bases + files tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-26 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    file_status = sa.Enum(
        "uploaded", "parsing", "parsed", "embedding", "indexed", "failed",
        name="file_status",
    )
    file_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_kb_owner_name_active",
        "knowledge_bases",
        ["owner_user_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "files",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "knowledge_base_id",
            sa.BigInteger,
            sa.ForeignKey("knowledge_bases.id"),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("extension", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("content_sha256", sa.Text, nullable=False),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column(
            "status",
            # PG_ENUM required: sa.Enum silently drops create_type=False in
            # SQLAlchemy 2.0.x, causing DuplicateObject on the already-created type.
            PG_ENUM(
                "uploaded", "parsing", "parsed", "embedding", "indexed", "failed",
                name="file_status",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'uploaded'"),
        ),
        sa.Column("status_error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_files_kb_filename_active",
        "files",
        ["knowledge_base_id", "filename"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_files_kb_filename_active", table_name="files")
    op.drop_table("files")
    op.drop_index("uq_kb_owner_name_active", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")
    sa.Enum(name="file_status").drop(op.get_bind(), checkfirst=True)
