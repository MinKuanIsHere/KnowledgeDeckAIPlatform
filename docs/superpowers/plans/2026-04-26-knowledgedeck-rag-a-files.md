# RAG Sub-project A — File Upload & Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver knowledge-base CRUD + per-KB file upload / list / delete with MinIO storage, matching the spec at [docs/superpowers/specs/2026-04-26-knowledgedeck-rag-a-files-design.md](../specs/2026-04-26-knowledgedeck-rag-a-files-design.md).

**Architecture:** Two new tables (`knowledge_bases`, `files`) with soft-delete columns; a thin `MinioClient` wrapper around `minio-py` (sync, called via `asyncio.to_thread`); two new FastAPI routers (`/knowledge-bases`, files nested under each KB); two new Next.js pages plus shared components reusing the existing axios + Zustand auth wiring.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + psycopg 3 + Alembic + minio-py + testcontainers MinIO + Next.js App Router + Zustand persist + axios + Vitest.

## Spec ↔ Existing-Pattern Reconciliation

The spec's "Error response format" section shows `{"detail": {"code": "...", "message": "..."}}` but states it "reuses the auth feature's existing shape". The existing auth code actually returns the simpler `{"detail": "code_string"}` shape (e.g. `{"detail": "invalid_credentials"}`). This plan follows the **existing** auth shape — `{"detail": "code_string"}` — for consistency. Frontend error handling continues to use the `ERROR_KEYS` / `ERROR_FALLBACKS` pattern from `frontend/app/login/page.tsx`. The spec example is treated as a documentation error, not a behavior change.

## Branching

Work directly on `dev` (per repo policy, no worktrees, no feature branches). Commit after each task. Run all tests before each commit.

## Decisions Carried From Spec

- Single-file multipart upload, nested `DELETE /knowledge-bases/{id}/files/{file_id}`.
- Soft-delete (`deleted_at TIMESTAMPTZ NULL`) on both `knowledge_bases` and `files`. KB delete cascades soft-mark to child files in one transaction. MinIO objects untouched.
- Format validation: extension allow-list (`txt`, `pdf`, `cs`) + PDF magic bytes (`%PDF` prefix) + TXT/CS no-NUL-in-first-1KB AND strict-UTF-8 decodable.
- 50 MiB single-file cap (`52_428_800` bytes), no per-KB count cap, no per-user quota.
- Duplicate filename in same KB → 409, enforced by `UNIQUE (knowledge_base_id, filename) WHERE deleted_at IS NULL`.
- MinIO key layout: `kb/{kb_id}/files/{file_id}/original.{ext}`.
- `file_status` enum defined fully now: `uploaded | parsing | parsed | embedding | indexed | failed`. A only writes `uploaded`.
- Tests use real MinIO via `testcontainers-python`'s MinIO container, parallel to the existing Postgres pattern.
- No new shadcn components — reuse the plain HTML + Tailwind pattern used by `frontend/app/login/page.tsx`.

## File Map

### Backend

- **Create**:
  - `backend/app/db/migrations/versions/0002_kb_files.py` — schema migration.
  - `backend/app/services/object_storage.py` — `MinioClient` async wrapper.
  - `backend/app/services/knowledge_base_service.py` — KB queries + soft-cascade delete.
  - `backend/app/services/file_service.py` — file validation pipeline + upload orchestration.
  - `backend/app/api/knowledge_bases.py` — KB router.
  - `backend/app/api/files.py` — files router (nested under KB id).
  - `backend/tests/test_models_kb_files.py` — schema smoke test.
  - `backend/tests/test_object_storage.py` — `MinioClient` happy path + error path.
  - `backend/tests/test_knowledge_bases.py` — endpoint tests.
  - `backend/tests/test_files_upload.py` — upload endpoint tests.
  - `backend/tests/test_files_list_delete.py` — list / delete endpoint tests.
- **Modify**:
  - `backend/app/db/models.py` — add `KnowledgeBase`, `KnowledgeFile`, `FileStatus`.
  - `backend/app/core/config.py` — add MinIO settings.
  - `backend/app/main.py` — register new routers.
  - `backend/app/startup.py` — call `MinioClient.ensure_bucket()` in lifespan.
  - `backend/tests/conftest.py` — add MinIO container fixture + autouse client patch + extend per-test TRUNCATE list.
  - `backend/pyproject.toml` — add `minio` runtime dep + `testcontainers[minio]` dev dep.

### Frontend

- **Create**:
  - `frontend/lib/knowledge-bases.ts` — typed axios client.
  - `frontend/lib/knowledge-bases.test.ts` — request shape tests.
  - `frontend/components/ConfirmDialog.tsx` + test — generic confirm modal.
  - `frontend/components/KnowledgeBaseList.tsx` + test.
  - `frontend/components/KnowledgeBaseCreateDialog.tsx` + test.
  - `frontend/components/FileUploadCard.tsx` + test.
  - `frontend/components/FileList.tsx` + test.
  - `frontend/app/(protected)/knowledge-bases/page.tsx`.
  - `frontend/app/(protected)/knowledge-bases/[id]/page.tsx`.
- **Modify**:
  - `frontend/app/(protected)/page.tsx` — make sidebar "Knowledge" item navigate to `/knowledge-bases`.

### Docs

- **Modify**:
  - `README.md` — short paragraph under setup pointing to the new pages (only if README already documents the chat shell — verify before editing).

---

## Task 1: Backend Dependencies + MinIO Settings

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_config.py` (extend existing)

- [ ] **Step 1: Add deps to pyproject.toml**

Edit `backend/pyproject.toml`:

```toml
[project]
name = "knowledgedeck-backend"
version = "0.1.0"
description = "FastAPI backend for KnowledgeDeck AI Platform"
requires-python = ">=3.11"
dependencies = [
    "alembic>=1.13.0",
    "fastapi>=0.115.0",
    "httpx>=0.27.0",
    "minio>=7.2.0",
    "psycopg[binary]>=3.2.0",
    "pydantic-settings>=2.4.0",
    "python-multipart>=0.0.20",
    "sqlalchemy>=2.0.32",
    "typer>=0.12.0",
    "uvicorn[standard]>=0.30.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "testcontainers[minio,postgresql]>=4.8.0",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
asyncio_mode = "auto"
```

`python-multipart` is required by FastAPI to parse `multipart/form-data` (file uploads).

- [ ] **Step 2: Reinstall deps**

Run: `cd backend && pip install -e ".[dev]"`
Expected: minio + python-multipart + testcontainers MinIO extras installed without errors.

- [ ] **Step 3: Write failing test for MinIO settings**

Append to `backend/tests/test_config.py`:

```python
def test_settings_expose_minio_fields(monkeypatch) -> None:
    from app.core.config import Settings

    monkeypatch.setenv("MINIO_ENDPOINT", "knowledgedeck_minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "k")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("MINIO_BUCKET", "kd-test")
    s = Settings()
    assert s.minio_endpoint == "knowledgedeck_minio:9000"
    assert s.minio_access_key == "k"
    assert s.minio_secret_key == "s"
    assert s.minio_bucket == "kd-test"
    assert s.max_upload_bytes == 52_428_800
```

- [ ] **Step 4: Run test to confirm failure**

Run: `cd backend && pytest tests/test_config.py::test_settings_expose_minio_fields -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'minio_endpoint'`.

- [ ] **Step 5: Add fields to Settings**

Edit `backend/app/core/config.py` — insert after the `cors_origins_list` property and before `llm_base_url`:

```python
    minio_endpoint: str = "knowledgedeck_minio:9000"
    minio_access_key: str = "change-me"
    minio_secret_key: str = "change-me"
    minio_bucket: str = "knowledgedeck"
    minio_secure: bool = False  # MVP runs MinIO over plain HTTP inside the compose network

    # 50 MiB hard cap on a single file upload.
    max_upload_bytes: int = 52_428_800
```

- [ ] **Step 6: Run all config tests**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app/core/config.py backend/tests/test_config.py
git commit -m "feat(backend): add MinIO + multipart deps and settings for RAG sub-project A

Adds minio runtime client, python-multipart for file uploads, and
testcontainers MinIO extra for tests. Introduces minio_* and
max_upload_bytes settings backed by existing .env values.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Database Schema + Models

**Files:**
- Create: `backend/app/db/migrations/versions/0002_kb_files.py`
- Modify: `backend/app/db/models.py`
- Create: `backend/tests/test_models_kb_files.py`

- [ ] **Step 1: Write failing model + migration smoke test**

Create `backend/tests/test_models_kb_files.py`:

```python
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
```

- [ ] **Step 2: Run test to confirm failure**

Run: `cd backend && pytest tests/test_models_kb_files.py -v`
Expected: FAIL with `ImportError` (KnowledgeBase / KnowledgeFile / FileStatus do not exist).

- [ ] **Step 3: Add models**

Edit `backend/app/db/models.py` — replace the entire file with:

```python
import enum
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FileStatus(enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    EMBEDDING = "embedding"
    INDEXED = "indexed"
    FAILED = "failed"


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    files: Mapped[list["KnowledgeFile"]] = relationship(
        back_populates="knowledge_base"
    )

    __table_args__ = (
        Index(
            "uq_kb_owner_name_active",
            "owner_user_id",
            "name",
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
    )


class KnowledgeFile(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("knowledge_bases.id"), nullable=False
    )
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    extension: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FileStatus] = mapped_column(
        SAEnum(
            FileStatus,
            name="file_status",
            create_type=False,  # the migration owns the type
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
        default=FileStatus.UPLOADED,
    )
    status_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    knowledge_base: Mapped[KnowledgeBase] = relationship(back_populates="files")

    __table_args__ = (
        Index(
            "uq_files_kb_filename_active",
            "knowledge_base_id",
            "filename",
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
    )
```

- [ ] **Step 4: Write the migration**

Create `backend/app/db/migrations/versions/0002_kb_files.py`:

```python
"""knowledge_bases + files tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-26 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

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
            sa.Enum(name="file_status", create_type=False, native_enum=True),
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
```

- [ ] **Step 5: Extend conftest TRUNCATE to include new tables**

Edit `backend/tests/conftest.py` — change the truncate inside `db_session`:

```python
        await setup.execute(text(
            "TRUNCATE TABLE files, knowledge_bases, users RESTART IDENTITY CASCADE"
        ))
```

(`CASCADE` is necessary because `files` and `knowledge_bases` reference `users` via FK.)

- [ ] **Step 6: Run all tests to verify migration applies and models work**

Run: `cd backend && pytest tests/test_models_kb_files.py tests/test_models.py tests/test_migration.py -v`
Expected: all green.

- [ ] **Step 7: Run the full backend test suite to catch regressions**

Run: `cd backend && pytest -v`
Expected: all green (pre-existing tests still pass with the new TRUNCATE column list).

- [ ] **Step 8: Commit**

```bash
git add backend/app/db/migrations/versions/0002_kb_files.py backend/app/db/models.py backend/tests/conftest.py backend/tests/test_models_kb_files.py
git commit -m "feat(backend): add knowledge_bases + files schema with soft delete

Introduces KnowledgeBase + KnowledgeFile models, file_status enum
(uploaded/parsing/parsed/embedding/indexed/failed), and partial unique
indexes that allow soft-deleted names/filenames to be reused.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: MinioClient Service

**Files:**
- Create: `backend/app/services/object_storage.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_object_storage.py`

- [ ] **Step 1: Add MinIO testcontainer fixture + autouse client patch**

Append to `backend/tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def minio_container():
    from testcontainers.minio import MinioContainer

    with MinioContainer("minio/minio:RELEASE.2024-10-13T13-34-11Z") as container:
        # Create the test bucket once per session so per-test code never sees
        # a "NoSuchBucket" error from MinIO. ensure_bucket() in lifespan only
        # runs in production startup; tests bypass lifespan via ASGITransport.
        client = container.get_client()
        if not client.bucket_exists("kd-test"):
            client.make_bucket("kd-test")
        yield container


@pytest.fixture(scope="session")
def minio_settings(minio_container) -> dict:
    config = minio_container.get_config()
    # `config` shape: {"endpoint": "host:port", "access_key": "...", "secret_key": "..."}
    return {
        "endpoint": config["endpoint"],
        "access_key": config["access_key"],
        "secret_key": config["secret_key"],
        "bucket": "kd-test",
    }


@pytest.fixture(autouse=True)
def _patch_app_storage(monkeypatch, minio_settings) -> None:
    """Point app.services.object_storage at the test MinIO container."""
    from app.services import object_storage as storage

    client = storage.MinioClient(
        endpoint=minio_settings["endpoint"],
        access_key=minio_settings["access_key"],
        secret_key=minio_settings["secret_key"],
        bucket=minio_settings["bucket"],
        secure=False,
    )
    monkeypatch.setattr(storage, "_client", client, raising=False)
```

If `testcontainers.minio.MinioContainer.get_config()` returns a different shape on the installed version, adjust the keys. The container exposes `get_client()` returning a `Minio` instance and `get_config()` returning a dict per testcontainers-python docs.

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_object_storage.py`:

```python
import io

import pytest

from app.services.object_storage import MinioClient, get_minio_client


@pytest.mark.asyncio
async def test_get_client_returns_patched_instance() -> None:
    client = get_minio_client()
    assert isinstance(client, MinioClient)


@pytest.mark.asyncio
async def test_ensure_bucket_is_idempotent() -> None:
    client = get_minio_client()
    await client.ensure_bucket()
    await client.ensure_bucket()  # second call must not raise


@pytest.mark.asyncio
async def test_put_then_delete_object_round_trip() -> None:
    client = get_minio_client()
    await client.ensure_bucket()
    payload = b"hello"
    await client.put_object(
        "kb/1/files/1/original.txt", io.BytesIO(payload), len(payload), "text/plain"
    )
    # Re-uploading same key must succeed (overwrite).
    await client.put_object(
        "kb/1/files/1/original.txt", io.BytesIO(payload), len(payload), "text/plain"
    )
    await client.delete_object("kb/1/files/1/original.txt")
    # Deleting twice must not raise (MinIO returns 204 on missing).
    await client.delete_object("kb/1/files/1/original.txt")


@pytest.mark.asyncio
async def test_put_object_propagates_failure() -> None:
    bad = MinioClient(
        endpoint="127.0.0.1:1",
        access_key="x",
        secret_key="x",
        bucket="kd-test",
        secure=False,
    )
    with pytest.raises(Exception):
        await bad.put_object("k", io.BytesIO(b""), 0, "application/octet-stream")
```

- [ ] **Step 3: Run tests to confirm failure**

Run: `cd backend && pytest tests/test_object_storage.py -v`
Expected: FAIL with `ImportError` (`MinioClient` does not exist).

- [ ] **Step 4: Implement MinioClient**

Create `backend/app/services/object_storage.py`:

```python
import asyncio
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings


class MinioClient:
    """Async-friendly wrapper over minio-py.

    minio-py is a sync library. Each public method runs the blocking call in
    a worker thread via asyncio.to_thread so it does not stall the FastAPI
    event loop.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
    ) -> None:
        self._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket = bucket

    @property
    def bucket(self) -> str:
        return self._bucket

    async def ensure_bucket(self) -> None:
        def _impl() -> None:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)

        await asyncio.to_thread(_impl)

    async def put_object(
        self,
        key: str,
        data: BinaryIO,
        length: int,
        content_type: str,
    ) -> None:
        def _impl() -> None:
            self._client.put_object(
                self._bucket, key, data, length, content_type=content_type
            )

        await asyncio.to_thread(_impl)

    async def delete_object(self, key: str) -> None:
        def _impl() -> None:
            try:
                self._client.remove_object(self._bucket, key)
            except S3Error as e:
                # NoSuchKey is fine — delete is idempotent for our purposes.
                if e.code != "NoSuchKey":
                    raise

        await asyncio.to_thread(_impl)


_client: MinioClient | None = None


def get_minio_client() -> MinioClient:
    """Process-wide MinioClient. Tests replace `_client` directly via conftest."""
    global _client
    if _client is None:
        s = get_settings()
        _client = MinioClient(
            endpoint=s.minio_endpoint,
            access_key=s.minio_access_key,
            secret_key=s.minio_secret_key,
            bucket=s.minio_bucket,
            secure=s.minio_secure,
        )
    return _client
```

- [ ] **Step 5: Wire `ensure_bucket` into the lifespan startup**

Edit `backend/app/startup.py` — replace the `lifespan` function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    factory = async_session_factory()
    async with factory() as session:
        await seed_initial_user(session)
        await session.commit()

    from app.services.object_storage import get_minio_client
    await get_minio_client().ensure_bucket()

    yield
```

The MinIO call is intentionally placed *after* DB seeding so DB issues surface first.

- [ ] **Step 6: Run object storage tests**

Run: `cd backend && pytest tests/test_object_storage.py -v`
Expected: all green.

- [ ] **Step 7: Run full backend tests**

Run: `cd backend && pytest -v`
Expected: all green. The MinIO container is shared session-scope so adds ~3s startup overhead, then is reused.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/object_storage.py backend/app/startup.py backend/tests/conftest.py backend/tests/test_object_storage.py
git commit -m "feat(backend): add MinioClient async wrapper + lifespan ensure_bucket

Wraps minio-py with asyncio.to_thread so file uploads never block the
event loop. Adds testcontainers-backed MinIO fixture so storage tests
hit real MinIO. Lifespan creates the bucket on first startup.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Knowledge Base Service + Endpoints

**Files:**
- Create: `backend/app/services/knowledge_base_service.py`
- Create: `backend/app/api/knowledge_bases.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_knowledge_bases.py`

- [ ] **Step 1: Write failing endpoint tests**

Create `backend/tests/test_knowledge_bases.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `cd backend && pytest tests/test_knowledge_bases.py -v`
Expected: FAIL — endpoints not yet defined (404 or import errors).

- [ ] **Step 3: Implement the service**

Create `backend/app/services/knowledge_base_service.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeBase, KnowledgeFile


async def create_knowledge_base(
    session: AsyncSession,
    *,
    owner_user_id: int,
    name: str,
    description: str | None,
) -> KnowledgeBase:
    kb = KnowledgeBase(
        owner_user_id=owner_user_id, name=name, description=description
    )
    session.add(kb)
    await session.flush()
    await session.commit()
    await session.refresh(kb)
    return kb


async def name_taken(session: AsyncSession, *, owner_user_id: int, name: str) -> bool:
    existing = await session.scalar(
        select(KnowledgeBase.id).where(
            KnowledgeBase.owner_user_id == owner_user_id,
            KnowledgeBase.name == name,
            KnowledgeBase.deleted_at.is_(None),
        )
    )
    return existing is not None


async def list_knowledge_bases(
    session: AsyncSession, *, owner_user_id: int
) -> list[tuple[KnowledgeBase, int]]:
    file_count = (
        select(
            KnowledgeFile.knowledge_base_id.label("kb_id"),
            func.count(KnowledgeFile.id).label("cnt"),
        )
        .where(KnowledgeFile.deleted_at.is_(None))
        .group_by(KnowledgeFile.knowledge_base_id)
        .subquery()
    )
    rows = await session.execute(
        select(KnowledgeBase, func.coalesce(file_count.c.cnt, 0))
        .outerjoin(file_count, file_count.c.kb_id == KnowledgeBase.id)
        .where(
            KnowledgeBase.owner_user_id == owner_user_id,
            KnowledgeBase.deleted_at.is_(None),
        )
        .order_by(KnowledgeBase.created_at.desc())
    )
    return [(kb, int(cnt)) for kb, cnt in rows.all()]


async def get_owned_kb(
    session: AsyncSession, *, owner_user_id: int, kb_id: int
) -> KnowledgeBase | None:
    return await session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_user_id == owner_user_id,
            KnowledgeBase.deleted_at.is_(None),
        )
    )


async def soft_delete_kb_cascade(
    session: AsyncSession, *, kb: KnowledgeBase
) -> None:
    now = datetime.now(timezone.utc)
    await session.execute(
        update(KnowledgeFile)
        .where(
            KnowledgeFile.knowledge_base_id == kb.id,
            KnowledgeFile.deleted_at.is_(None),
        )
        .values(deleted_at=now)
    )
    kb.deleted_at = now
    await session.commit()
```

- [ ] **Step 4: Implement the router**

Create `backend/app/api/knowledge_bases.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.db.models import User
from app.services import knowledge_base_service as svc

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class KnowledgeBaseOut(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: str


class KnowledgeBaseListItem(KnowledgeBaseOut):
    file_count: int


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
async def create_kb(
    body: KnowledgeBaseCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> KnowledgeBaseOut:
    if await svc.name_taken(session, owner_user_id=user.id, name=body.name):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="duplicate_kb_name")
    kb = await svc.create_knowledge_base(
        session,
        owner_user_id=user.id,
        name=body.name,
        description=body.description,
    )
    return KnowledgeBaseOut(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        created_at=kb.created_at.isoformat(),
    )


@router.get("", response_model=list[KnowledgeBaseListItem])
async def list_kbs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[KnowledgeBaseListItem]:
    items = await svc.list_knowledge_bases(session, owner_user_id=user.id)
    return [
        KnowledgeBaseListItem(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            created_at=kb.created_at.isoformat(),
            file_count=cnt,
        )
        for kb, cnt in items
    ]


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb(
    kb_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    kb = await svc.get_owned_kb(session, owner_user_id=user.id, kb_id=kb_id)
    if kb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="kb_not_found")
    await svc.soft_delete_kb_cascade(session, kb=kb)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: Register the router**

Edit `backend/app/main.py` — add an import and `include_router` call:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.knowledge_bases import router as knowledge_bases_router
from app.core.config import get_settings
from app.startup import lifespan


def create_app() -> FastAPI:
    app = FastAPI(title="KnowledgeDeck API", version="0.1.0", lifespan=lifespan)

    origins = get_settings().cors_origins_list
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["Authorization", "Content-Type"],
        )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(knowledge_bases_router)
    return app


app = create_app()
```

- [ ] **Step 6: Run the new tests**

Run: `cd backend && pytest tests/test_knowledge_bases.py -v`
Expected: all green.

- [ ] **Step 7: Run the full backend test suite**

Run: `cd backend && pytest -v`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/knowledge_base_service.py backend/app/api/knowledge_bases.py backend/app/main.py backend/tests/test_knowledge_bases.py
git commit -m "feat(backend): add knowledge_bases CRUD endpoints

POST/GET/DELETE /knowledge-bases with soft-delete cascade. Owner
isolation surfaces other users' KBs as 404 (not 403). file_count is
computed via outer join + count for list endpoint.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: File Upload Endpoint + Validators

**Files:**
- Create: `backend/app/services/file_service.py`
- Create: `backend/app/api/files.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_files_upload.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_files_upload.py`:

```python
import io

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


async def make_kb(http_client: AsyncClient, user: User, name: str = "K") -> int:
    res = await http_client.post(
        "/knowledge-bases", json={"name": name}, headers=auth(user)
    )
    return res.json()["id"]


PDF_BYTES = b"%PDF-1.4\n%EOF\n"
TXT_BYTES = b"hello world\n"
CS_BYTES = b"using System;\nclass A {}\n"


@pytest.mark.asyncio
async def test_upload_pdf_happy_path(http_client, alice: User) -> None:
    kb_id = await make_kb(http_client, alice)
    res = await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("doc.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
        headers=auth(alice),
    )
    assert res.status_code == 201
    body = res.json()
    assert body["filename"] == "doc.pdf"
    assert body["extension"] == "pdf"
    assert body["size_bytes"] == len(PDF_BYTES)
    assert body["status"] == "uploaded"


@pytest.mark.asyncio
async def test_upload_txt_happy_path(http_client, alice: User) -> None:
    kb_id = await make_kb(http_client, alice)
    res = await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("note.txt", io.BytesIO(TXT_BYTES), "text/plain")},
        headers=auth(alice),
    )
    assert res.status_code == 201


@pytest.mark.asyncio
async def test_upload_cs_happy_path(http_client, alice: User) -> None:
    kb_id = await make_kb(http_client, alice)
    res = await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("Program.cs", io.BytesIO(CS_BYTES), "text/x-csharp")},
        headers=auth(alice),
    )
    assert res.status_code == 201


@pytest.mark.asyncio
async def test_upload_rejects_unknown_extension(http_client, alice: User) -> None:
    kb_id = await make_kb(http_client, alice)
    res = await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("x.docx", io.BytesIO(b"PK\x03\x04"), "application/octet-stream")},
        headers=auth(alice),
    )
    assert res.status_code == 400
    assert res.json() == {"detail": "invalid_extension"}


@pytest.mark.asyncio
async def test_upload_rejects_pdf_without_magic(http_client, alice: User) -> None:
    kb_id = await make_kb(http_client, alice)
    res = await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("evil.pdf", io.BytesIO(b"NOT-A-PDF"), "application/pdf")},
        headers=auth(alice),
    )
    assert res.status_code == 400
    assert res.json() == {"detail": "invalid_content"}


@pytest.mark.asyncio
async def test_upload_rejects_txt_with_null_byte(http_client, alice: User) -> None:
    kb_id = await make_kb(http_client, alice)
    res = await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("bad.txt", io.BytesIO(b"hello\x00world"), "text/plain")},
        headers=auth(alice),
    )
    assert res.status_code == 400
    assert res.json() == {"detail": "invalid_content"}


@pytest.mark.asyncio
async def test_upload_rejects_txt_not_utf8(http_client, alice: User) -> None:
    kb_id = await make_kb(http_client, alice)
    bad = b"\xff\xfe\xfd not utf-8"
    res = await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("bad.txt", io.BytesIO(bad), "text/plain")},
        headers=auth(alice),
    )
    assert res.status_code == 400
    assert res.json() == {"detail": "invalid_content"}


@pytest.mark.asyncio
async def test_upload_rejects_oversize(http_client, alice: User, monkeypatch) -> None:
    # Lower the cap for the test instead of streaming 50 MiB.
    from app.api import files as files_module
    monkeypatch.setattr(files_module, "MAX_UPLOAD_BYTES", 100)
    kb_id = await make_kb(http_client, alice)
    res = await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("big.txt", io.BytesIO(b"a" * 200), "text/plain")},
        headers=auth(alice),
    )
    assert res.status_code == 413
    assert res.json() == {"detail": "file_too_large"}


@pytest.mark.asyncio
async def test_upload_rejects_duplicate_filename(http_client, alice: User) -> None:
    kb_id = await make_kb(http_client, alice)
    await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("x.txt", io.BytesIO(TXT_BYTES), "text/plain")},
        headers=auth(alice),
    )
    res = await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("x.txt", io.BytesIO(TXT_BYTES), "text/plain")},
        headers=auth(alice),
    )
    assert res.status_code == 409
    assert res.json() == {"detail": "duplicate_filename"}


@pytest.mark.asyncio
async def test_upload_to_other_users_kb_returns_404(
    http_client, alice: User, bob: User
) -> None:
    kb_id = await make_kb(http_client, alice)
    res = await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("x.txt", io.BytesIO(TXT_BYTES), "text/plain")},
        headers=auth(bob),
    )
    assert res.status_code == 404
    assert res.json() == {"detail": "kb_not_found"}


@pytest.mark.asyncio
async def test_upload_rolls_back_db_when_minio_put_fails(
    http_client, alice: User, db_session, monkeypatch
) -> None:
    from sqlalchemy import select

    from app.db.models import KnowledgeFile
    from app.services import object_storage as storage

    async def boom(*args, **kwargs):
        raise RuntimeError("simulated minio outage")

    monkeypatch.setattr(storage.MinioClient, "put_object", boom, raising=True)
    kb_id = await make_kb(http_client, alice)
    res = await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("x.txt", io.BytesIO(TXT_BYTES), "text/plain")},
        headers=auth(alice),
    )
    assert res.status_code == 500
    rows = await db_session.execute(
        select(KnowledgeFile).where(KnowledgeFile.knowledge_base_id == kb_id)
    )
    assert rows.all() == []
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `cd backend && pytest tests/test_files_upload.py -v`
Expected: FAIL — file router not defined.

- [ ] **Step 3: Implement the validators + service**

Create `backend/app/services/file_service.py`:

```python
import hashlib
import io

ALLOWED_EXTENSIONS = {"txt", "pdf", "cs"}


class ValidationError(Exception):
    """Raised by validators with a stable string code (e.g. invalid_extension)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def normalize_extension(filename: str) -> str:
    """Return the lowercased extension without leading dot, or "" if none."""
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def validate_extension(filename: str) -> str:
    ext = normalize_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("invalid_extension")
    return ext


def validate_content(extension: str, head: bytes) -> None:
    """`head` is the first ~1 KiB of the upload."""
    if extension == "pdf":
        if not head.startswith(b"%PDF"):
            raise ValidationError("invalid_content")
        return
    # txt / cs share the text-likeness rule.
    sample = head[:1024]
    if b"\x00" in sample:
        raise ValidationError("invalid_content")
    try:
        sample.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        raise ValidationError("invalid_content") from e


async def stream_into_buffer(
    upload, max_bytes: int
) -> tuple[bytes, str, int]:
    """Read the multipart upload into memory while enforcing the size cap.

    Returns (data, sha256_hex, size_bytes). Raises ValidationError("file_too_large")
    if the upload exceeds `max_bytes`.
    """
    hasher = hashlib.sha256()
    buf = io.BytesIO()
    total = 0
    chunk_size = 64 * 1024
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationError("file_too_large")
        hasher.update(chunk)
        buf.write(chunk)
    return buf.getvalue(), hasher.hexdigest(), total
```

Create `backend/app/api/files.py`:

```python
import io

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.base import get_db
from app.db.models import FileStatus, KnowledgeBase, KnowledgeFile, User
from app.services import file_service
from app.services.object_storage import get_minio_client

router = APIRouter(prefix="/knowledge-bases", tags=["files"])

# Module-level so tests can monkeypatch a smaller value.
MAX_UPLOAD_BYTES = get_settings().max_upload_bytes


class FileOut(BaseModel):
    id: int
    knowledge_base_id: int
    filename: str
    extension: str
    size_bytes: int
    status: str
    status_error: str | None = None
    created_at: str


def _content_type_for(extension: str) -> str:
    return {
        "pdf": "application/pdf",
        "txt": "text/plain; charset=utf-8",
        "cs": "text/x-csharp; charset=utf-8",
    }[extension]


async def _load_owned_kb(
    session: AsyncSession, *, owner_user_id: int, kb_id: int
) -> KnowledgeBase:
    kb = await session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_user_id == owner_user_id,
            KnowledgeBase.deleted_at.is_(None),
        )
    )
    if kb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="kb_not_found")
    return kb


@router.post(
    "/{kb_id}/files", response_model=FileOut, status_code=status.HTTP_201_CREATED
)
async def upload_file(
    kb_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FileOut:
    kb = await _load_owned_kb(session, owner_user_id=user.id, kb_id=kb_id)

    try:
        extension = file_service.validate_extension(file.filename or "")
    except file_service.ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=e.code)

    try:
        data, sha256, size = await file_service.stream_into_buffer(
            file, MAX_UPLOAD_BYTES
        )
    except file_service.ValidationError as e:
        # `stream_into_buffer` only raises file_too_large.
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=e.code)

    try:
        file_service.validate_content(extension, data[:1024])
    except file_service.ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=e.code)

    duplicate = await session.scalar(
        select(KnowledgeFile.id).where(
            KnowledgeFile.knowledge_base_id == kb.id,
            KnowledgeFile.filename == file.filename,
            KnowledgeFile.deleted_at.is_(None),
        )
    )
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="duplicate_filename")

    row = KnowledgeFile(
        knowledge_base_id=kb.id,
        owner_user_id=user.id,
        filename=file.filename,
        extension=extension,
        size_bytes=size,
        content_sha256=sha256,
        storage_key="",  # placeholder — updated after we know the id
        status=FileStatus.UPLOADED,
    )
    session.add(row)
    await session.flush()
    row.storage_key = f"kb/{kb.id}/files/{row.id}/original.{extension}"

    try:
        await get_minio_client().put_object(
            row.storage_key,
            io.BytesIO(data),
            size,
            _content_type_for(extension),
        )
    except Exception:
        await session.rollback()
        raise

    await session.commit()
    await session.refresh(row)

    return FileOut(
        id=row.id,
        knowledge_base_id=row.knowledge_base_id,
        filename=row.filename,
        extension=row.extension,
        size_bytes=row.size_bytes,
        status=row.status.value,
        status_error=row.status_error,
        created_at=row.created_at.isoformat(),
    )
```

- [ ] **Step 4: Register the router**

Edit `backend/app/main.py` — add the import and include:

```python
from app.api.files import router as files_router
# ...
    app.include_router(files_router)
```

Place the include after `knowledge_bases_router`.

- [ ] **Step 5: Run upload tests**

Run: `cd backend && pytest tests/test_files_upload.py -v`
Expected: all green. Watch the rollback test in particular — it must verify the row count is 0 after the simulated MinIO failure.

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && pytest -v`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/file_service.py backend/app/api/files.py backend/app/main.py backend/tests/test_files_upload.py
git commit -m "feat(backend): add file upload endpoint with validation + MinIO storage

POST /knowledge-bases/{id}/files. Pipeline: extension allow-list →
streamed read with 50 MiB cap + sha256 → content sniff (PDF magic
bytes / TXT-CS UTF-8 strict + no NUL byte) → duplicate-filename
check → INSERT row + flush for id → set storage_key → MinIO PUT →
COMMIT. MinIO failure rolls back the DB row.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: File List + Delete Endpoints

**Files:**
- Modify: `backend/app/api/files.py`
- Create: `backend/tests/test_files_list_delete.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_files_list_delete.py`:

```python
import io

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


TXT = b"hello\n"


async def make_kb_and_file(client, user, *, kb_name="K", filename="x.txt") -> tuple[int, int]:
    kb = await client.post(
        "/knowledge-bases", json={"name": kb_name}, headers=auth(user)
    )
    kb_id = kb.json()["id"]
    f = await client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": (filename, io.BytesIO(TXT), "text/plain")},
        headers=auth(user),
    )
    return kb_id, f.json()["id"]


@pytest.mark.asyncio
async def test_list_files_returns_only_non_deleted(http_client, alice: User) -> None:
    kb_id, file_id = await make_kb_and_file(http_client, alice)
    await http_client.post(
        f"/knowledge-bases/{kb_id}/files",
        files={"file": ("y.txt", io.BytesIO(TXT), "text/plain")},
        headers=auth(alice),
    )
    res = await http_client.get(
        f"/knowledge-bases/{kb_id}/files", headers=auth(alice)
    )
    assert res.status_code == 200
    body = res.json()
    assert {b["filename"] for b in body} == {"x.txt", "y.txt"}
    await http_client.delete(
        f"/knowledge-bases/{kb_id}/files/{file_id}", headers=auth(alice)
    )
    res = await http_client.get(
        f"/knowledge-bases/{kb_id}/files", headers=auth(alice)
    )
    assert {b["filename"] for b in res.json()} == {"y.txt"}


@pytest.mark.asyncio
async def test_delete_file_returns_204(http_client, alice: User) -> None:
    kb_id, file_id = await make_kb_and_file(http_client, alice)
    res = await http_client.delete(
        f"/knowledge-bases/{kb_id}/files/{file_id}", headers=auth(alice)
    )
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_delete_file_other_user_returns_404(
    http_client, alice: User, bob: User
) -> None:
    kb_id, file_id = await make_kb_and_file(http_client, alice)
    res = await http_client.delete(
        f"/knowledge-bases/{kb_id}/files/{file_id}", headers=auth(bob)
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_file_twice_returns_404(http_client, alice: User) -> None:
    kb_id, file_id = await make_kb_and_file(http_client, alice)
    await http_client.delete(
        f"/knowledge-bases/{kb_id}/files/{file_id}", headers=auth(alice)
    )
    res = await http_client.delete(
        f"/knowledge-bases/{kb_id}/files/{file_id}", headers=auth(alice)
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_kb_delete_cascades_to_files(http_client, alice: User) -> None:
    kb_id, _ = await make_kb_and_file(http_client, alice)
    await http_client.delete(f"/knowledge-bases/{kb_id}", headers=auth(alice))
    # KB now hidden — listing files would also 404 because KB lookup fails first.
    res = await http_client.get(
        f"/knowledge-bases/{kb_id}/files", headers=auth(alice)
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_files_other_user_returns_404(
    http_client, alice: User, bob: User
) -> None:
    kb_id, _ = await make_kb_and_file(http_client, alice)
    res = await http_client.get(
        f"/knowledge-bases/{kb_id}/files", headers=auth(bob)
    )
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `cd backend && pytest tests/test_files_list_delete.py -v`
Expected: FAIL — list/delete endpoints not yet defined.

- [ ] **Step 3: Add list + delete endpoints**

Append to `backend/app/api/files.py`:

```python
from datetime import datetime, timezone


@router.get("/{kb_id}/files", response_model=list[FileOut])
async def list_files(
    kb_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[FileOut]:
    await _load_owned_kb(session, owner_user_id=user.id, kb_id=kb_id)
    rows = await session.scalars(
        select(KnowledgeFile)
        .where(
            KnowledgeFile.knowledge_base_id == kb_id,
            KnowledgeFile.deleted_at.is_(None),
        )
        .order_by(KnowledgeFile.created_at.desc())
    )
    return [
        FileOut(
            id=r.id,
            knowledge_base_id=r.knowledge_base_id,
            filename=r.filename,
            extension=r.extension,
            size_bytes=r.size_bytes,
            status=r.status.value,
            status_error=r.status_error,
            created_at=r.created_at.isoformat(),
        )
        for r in rows.all()
    ]


@router.delete("/{kb_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    kb_id: int,
    file_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await _load_owned_kb(session, owner_user_id=user.id, kb_id=kb_id)
    row = await session.scalar(
        select(KnowledgeFile).where(
            KnowledgeFile.id == file_id,
            KnowledgeFile.knowledge_base_id == kb_id,
            KnowledgeFile.deleted_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="file_not_found")
    row.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Move the `from datetime import datetime, timezone` import to the top of the file with the other imports (don't leave it duplicated mid-file).

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_files_list_delete.py -v`
Expected: all green.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && pytest -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/files.py backend/tests/test_files_list_delete.py
git commit -m "feat(backend): add file list + soft-delete endpoints

GET /knowledge-bases/{id}/files lists non-deleted files.
DELETE /knowledge-bases/{id}/files/{file_id} marks deleted_at.
KB ownership check runs first so cross-user requests return 404
without leaking file existence.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Frontend API Client

**Files:**
- Create: `frontend/lib/knowledge-bases.ts`
- Create: `frontend/lib/knowledge-bases.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/lib/knowledge-bases.test.ts`:

```typescript
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { api } from "./api";
import {
  createKnowledgeBase,
  deleteFile,
  deleteKnowledgeBase,
  listFiles,
  listKnowledgeBases,
  uploadFile,
} from "./knowledge-bases";

describe("knowledge-bases API client", () => {
  let mock: MockAdapter;

  beforeEach(() => {
    mock = new MockAdapter(api);
  });

  afterEach(() => {
    mock.restore();
  });

  it("listKnowledgeBases hits GET /knowledge-bases", async () => {
    mock.onGet("/knowledge-bases").reply(200, [
      { id: 1, name: "A", description: null, file_count: 0, created_at: "t" },
    ]);
    const out = await listKnowledgeBases();
    expect(out).toHaveLength(1);
    expect(out[0]).toEqual({
      id: 1, name: "A", description: null, file_count: 0, created_at: "t",
    });
  });

  it("createKnowledgeBase POSTs name + description", async () => {
    mock.onPost("/knowledge-bases").reply((config) => {
      expect(JSON.parse(config.data)).toEqual({ name: "New", description: "d" });
      return [201, { id: 2, name: "New", description: "d", created_at: "t" }];
    });
    const out = await createKnowledgeBase({ name: "New", description: "d" });
    expect(out.id).toBe(2);
  });

  it("deleteKnowledgeBase hits DELETE /knowledge-bases/:id", async () => {
    mock.onDelete("/knowledge-bases/5").reply(204);
    await deleteKnowledgeBase(5);
  });

  it("listFiles hits GET /knowledge-bases/:id/files", async () => {
    mock.onGet("/knowledge-bases/3/files").reply(200, []);
    const out = await listFiles(3);
    expect(out).toEqual([]);
  });

  it("uploadFile sends multipart with file field", async () => {
    mock.onPost("/knowledge-bases/3/files").reply((config) => {
      expect(config.data).toBeInstanceOf(FormData);
      expect(config.data.get("file")).toBeInstanceOf(File);
      return [201, {
        id: 9, knowledge_base_id: 3, filename: "x.txt", extension: "txt",
        size_bytes: 1, status: "uploaded", status_error: null, created_at: "t",
      }];
    });
    const f = new File(["x"], "x.txt", { type: "text/plain" });
    const out = await uploadFile(3, f);
    expect(out.id).toBe(9);
  });

  it("uploadFile invokes onProgress with percentages", async () => {
    let lastPct = -1;
    mock.onPost("/knowledge-bases/3/files").reply((config) => {
      // Simulate axios progress event firing.
      config.onUploadProgress?.({ loaded: 50, total: 100 } as ProgressEvent);
      config.onUploadProgress?.({ loaded: 100, total: 100 } as ProgressEvent);
      return [201, {
        id: 9, knowledge_base_id: 3, filename: "x.txt", extension: "txt",
        size_bytes: 1, status: "uploaded", status_error: null, created_at: "t",
      }];
    });
    await uploadFile(3, new File(["x"], "x.txt"), (pct) => { lastPct = pct; });
    expect(lastPct).toBe(100);
  });

  it("deleteFile hits DELETE /knowledge-bases/:kb/files/:file", async () => {
    mock.onDelete("/knowledge-bases/3/files/9").reply(204);
    await deleteFile(3, 9);
  });
});
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `cd frontend && npm test -- knowledge-bases.test`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the client**

Create `frontend/lib/knowledge-bases.ts`:

```typescript
import { api } from "./api";

export type KnowledgeBase = {
  id: number;
  name: string;
  description: string | null;
  file_count: number;
  created_at: string;
};

export type KnowledgeBaseCreated = {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
};

export type KnowledgeFile = {
  id: number;
  knowledge_base_id: number;
  filename: string;
  extension: string;
  size_bytes: number;
  status: string;
  status_error: string | null;
  created_at: string;
};

export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  const res = await api.get<KnowledgeBase[]>("/knowledge-bases");
  return res.data;
}

export async function createKnowledgeBase(input: {
  name: string;
  description?: string | null;
}): Promise<KnowledgeBaseCreated> {
  const res = await api.post<KnowledgeBaseCreated>("/knowledge-bases", {
    name: input.name,
    description: input.description ?? null,
  });
  return res.data;
}

export async function deleteKnowledgeBase(id: number): Promise<void> {
  await api.delete(`/knowledge-bases/${id}`);
}

export async function listFiles(kbId: number): Promise<KnowledgeFile[]> {
  const res = await api.get<KnowledgeFile[]>(`/knowledge-bases/${kbId}/files`);
  return res.data;
}

export async function uploadFile(
  kbId: number,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<KnowledgeFile> {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post<KnowledgeFile>(
    `/knowledge-bases/${kbId}/files`,
    form,
    {
      onUploadProgress: (e) => {
        if (!onProgress || !e.total) return;
        onProgress(Math.round((e.loaded / e.total) * 100));
      },
    },
  );
  return res.data;
}

export async function deleteFile(kbId: number, fileId: number): Promise<void> {
  await api.delete(`/knowledge-bases/${kbId}/files/${fileId}`);
}
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- knowledge-bases.test`
Expected: all green.

- [ ] **Step 5: Run the full frontend test suite**

Run: `cd frontend && npm test`
Expected: all green.

- [ ] **Step 6: Run typecheck**

Run: `cd frontend && npm run typecheck`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/knowledge-bases.ts frontend/lib/knowledge-bases.test.ts
git commit -m "feat(frontend): add knowledge-bases axios client + types

Typed wrappers over /knowledge-bases endpoints. uploadFile uses
FormData and forwards axios upload progress as 0-100 percent for the
caller to render.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Shared Confirm Dialog Component

**Files:**
- Create: `frontend/components/ConfirmDialog.tsx`
- Create: `frontend/components/ConfirmDialog.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/components/ConfirmDialog.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("renders title and message and calls onConfirm", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Delete X?"
        message="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    expect(screen.getByText("Delete X?")).toBeInTheDocument();
    expect(screen.getByText("This cannot be undone.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when Cancel clicked", async () => {
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Delete?"
        message=""
        onConfirm={() => {}}
        onCancel={onCancel}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when open=false", () => {
    const { container } = render(
      <ConfirmDialog
        open={false}
        title="Delete?"
        message=""
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `cd frontend && npm test -- ConfirmDialog.test`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

Create `frontend/components/ConfirmDialog.tsx`:

```typescript
"use client";

type Props = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open, title, message, confirmLabel = "Confirm", onConfirm, onCancel,
}: Props) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className="w-full max-w-sm rounded-lg border border-border bg-white p-5 shadow-lg">
        <h2 id="confirm-dialog-title" className="text-base font-semibold">
          {title}
        </h2>
        {message ? (
          <p className="mt-2 text-sm text-muted-foreground">{message}</p>
        ) : null}
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-border bg-white px-3 py-1.5 text-sm hover:bg-muted"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-md bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- ConfirmDialog.test`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ConfirmDialog.tsx frontend/components/ConfirmDialog.test.tsx
git commit -m "feat(frontend): add ConfirmDialog component for delete prompts

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Knowledge Base List Page + Components

**Files:**
- Create: `frontend/components/KnowledgeBaseList.tsx`
- Create: `frontend/components/KnowledgeBaseList.test.tsx`
- Create: `frontend/components/KnowledgeBaseCreateDialog.tsx`
- Create: `frontend/components/KnowledgeBaseCreateDialog.test.tsx`
- Create: `frontend/app/(protected)/knowledge-bases/page.tsx`

- [ ] **Step 1: Write failing tests for KnowledgeBaseCreateDialog**

Create `frontend/components/KnowledgeBaseCreateDialog.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { KnowledgeBaseCreateDialog } from "./KnowledgeBaseCreateDialog";

describe("KnowledgeBaseCreateDialog", () => {
  it("does not render when open=false", () => {
    const { container } = render(
      <KnowledgeBaseCreateDialog
        open={false}
        onSubmit={() => Promise.resolve()}
        onClose={() => {}}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("rejects empty name", async () => {
    const onSubmit = vi.fn();
    render(
      <KnowledgeBaseCreateDialog
        open
        onSubmit={onSubmit}
        onClose={() => {}}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits trimmed name + description", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(
      <KnowledgeBaseCreateDialog open onSubmit={onSubmit} onClose={onClose} />,
    );
    await userEvent.type(screen.getByLabelText("Name"), "  Notes  ");
    await userEvent.type(screen.getByLabelText("Description"), "personal");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(onSubmit).toHaveBeenCalledWith({
      name: "Notes", description: "personal",
    });
  });

  it("renders error message from onSubmit rejection", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("duplicate_kb_name"));
    render(
      <KnowledgeBaseCreateDialog open onSubmit={onSubmit} onClose={() => {}} />,
    );
    await userEvent.type(screen.getByLabelText("Name"), "Notes");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(
      await screen.findByText("A knowledge base with this name already exists"),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement KnowledgeBaseCreateDialog**

Create `frontend/components/KnowledgeBaseCreateDialog.tsx`:

```typescript
"use client";

import { useState, type FormEvent } from "react";
import { isAxiosError } from "axios";

const ERROR_FALLBACKS: Record<string, string> = {
  duplicate_kb_name: "A knowledge base with this name already exists",
};

type Props = {
  open: boolean;
  onSubmit: (input: { name: string; description: string | null }) => Promise<void>;
  onClose: () => void;
};

function extractErrorCode(err: unknown): string | null {
  if (err instanceof Error && err.message in ERROR_FALLBACKS) return err.message;
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}

export function KnowledgeBaseCreateDialog({ open, onSubmit, onClose }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErrorCode(null);
    const trimmedName = name.trim();
    const trimmedDesc = description.trim();
    if (!trimmedName) return;
    setSubmitting(true);
    try {
      await onSubmit({
        name: trimmedName,
        description: trimmedDesc || null,
      });
      setName("");
      setDescription("");
      onClose();
    } catch (err) {
      setErrorCode(extractErrorCode(err) ?? "unknown");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
    >
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md space-y-3 rounded-lg border border-border bg-white p-5 shadow-lg"
        aria-label="Create knowledge base"
      >
        <h2 className="text-base font-semibold">New knowledge base</h2>
        <div className="space-y-1">
          <label htmlFor="kb-name" className="block text-sm">Name</label>
          <input
            id="kb-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="kb-desc" className="block text-sm">Description</label>
          <textarea
            id="kb-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={500}
            rows={3}
            className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm"
          />
        </div>
        {errorCode ? (
          <div className="text-sm text-red-600" data-testid="kb-create-error">
            {ERROR_FALLBACKS[errorCode] ?? "Could not create knowledge base"}
          </div>
        ) : null}
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border bg-white px-3 py-1.5 text-sm hover:bg-muted"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-foreground px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {submitting ? "..." : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Run dialog tests**

Run: `cd frontend && npm test -- KnowledgeBaseCreateDialog.test`
Expected: all green.

- [ ] **Step 4: Write failing tests for KnowledgeBaseList**

Create `frontend/components/KnowledgeBaseList.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { KnowledgeBaseList } from "./KnowledgeBaseList";

const item = (id: number, name: string, file_count = 0) => ({
  id, name, description: null, file_count, created_at: "2026-04-26T00:00:00Z",
});

describe("KnowledgeBaseList", () => {
  it("renders empty state", () => {
    render(<KnowledgeBaseList items={[]} onOpen={() => {}} onDelete={() => {}} />);
    expect(screen.getByText(/no knowledge bases/i)).toBeInTheDocument();
  });

  it("renders rows with file_count", () => {
    render(
      <KnowledgeBaseList
        items={[item(1, "A", 3), item(2, "B")]}
        onOpen={() => {}}
        onDelete={() => {}}
      />,
    );
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
    expect(screen.getByText("3 files")).toBeInTheDocument();
    expect(screen.getByText("0 files")).toBeInTheDocument();
  });

  it("calls onOpen with id when row clicked", async () => {
    const onOpen = vi.fn();
    const u = (await import("@testing-library/user-event")).default;
    render(
      <KnowledgeBaseList items={[item(7, "X")]} onOpen={onOpen} onDelete={() => {}} />,
    );
    await u.click(screen.getByRole("button", { name: /open x/i }));
    expect(onOpen).toHaveBeenCalledWith(7);
  });

  it("calls onDelete with id when delete clicked", async () => {
    const onDelete = vi.fn();
    const u = (await import("@testing-library/user-event")).default;
    render(
      <KnowledgeBaseList items={[item(7, "X")]} onOpen={() => {}} onDelete={onDelete} />,
    );
    await u.click(screen.getByRole("button", { name: /delete x/i }));
    expect(onDelete).toHaveBeenCalledWith(7);
  });
});
```

- [ ] **Step 5: Implement KnowledgeBaseList**

Create `frontend/components/KnowledgeBaseList.tsx`:

```typescript
"use client";

import type { KnowledgeBase } from "../lib/knowledge-bases";

type Props = {
  items: KnowledgeBase[];
  onOpen: (id: number) => void;
  onDelete: (id: number) => void;
};

export function KnowledgeBaseList({ items, onOpen, onDelete }: Props) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-white p-8 text-center text-sm text-muted-foreground">
        No knowledge bases yet. Click "+ New" to create one.
      </div>
    );
  }
  return (
    <ul className="divide-y divide-border rounded-lg border border-border bg-white">
      {items.map((kb) => (
        <li key={kb.id} className="flex items-center justify-between px-4 py-3">
          <button
            type="button"
            onClick={() => onOpen(kb.id)}
            aria-label={`Open ${kb.name}`}
            className="flex-1 text-left"
          >
            <div className="text-sm font-medium">{kb.name}</div>
            <div className="text-xs text-muted-foreground">
              {kb.file_count} {kb.file_count === 1 ? "file" : "files"}
              {kb.description ? ` · ${kb.description}` : ""}
            </div>
          </button>
          <button
            type="button"
            onClick={() => onDelete(kb.id)}
            aria-label={`Delete ${kb.name}`}
            className="ml-3 rounded-md border border-border px-2 py-1 text-xs text-red-600 hover:bg-red-50"
          >
            Delete
          </button>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 6: Run list tests**

Run: `cd frontend && npm test -- KnowledgeBaseList.test`
Expected: all green.

- [ ] **Step 7: Implement the page**

Create `frontend/app/(protected)/knowledge-bases/page.tsx`:

```typescript
"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ConfirmDialog } from "../../../components/ConfirmDialog";
import { KnowledgeBaseCreateDialog } from "../../../components/KnowledgeBaseCreateDialog";
import { KnowledgeBaseList } from "../../../components/KnowledgeBaseList";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  listKnowledgeBases,
  type KnowledgeBase,
} from "../../../lib/knowledge-bases";

export default function KnowledgeBasesPage() {
  const router = useRouter();
  const [items, setItems] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeBase | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      setItems(await listKnowledgeBases());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(input: { name: string; description: string | null }) {
    await createKnowledgeBase(input);
    await refresh();
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    const id = deleteTarget.id;
    setDeleteTarget(null);
    await deleteKnowledgeBase(id);
    await refresh();
  }

  return (
    <main className="min-h-screen bg-background p-6 text-foreground">
      <div className="mx-auto max-w-3xl space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Knowledge Bases</h1>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="rounded-md bg-foreground px-3 py-1.5 text-sm text-white"
          >
            + New
          </button>
        </div>
        {loading ? (
          <div className="text-sm text-muted-foreground">Loading…</div>
        ) : (
          <KnowledgeBaseList
            items={items}
            onOpen={(id) => router.push(`/knowledge-bases/${id}`)}
            onDelete={(id) => {
              const target = items.find((kb) => kb.id === id);
              if (target) setDeleteTarget(target);
            }}
          />
        )}
      </div>
      <KnowledgeBaseCreateDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSubmit={handleCreate}
      />
      <ConfirmDialog
        open={deleteTarget !== null}
        title={deleteTarget ? `Delete "${deleteTarget.name}"?` : ""}
        message="All files in this knowledge base will be deleted. This cannot be undone."
        confirmLabel="Delete"
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </main>
  );
}
```

- [ ] **Step 8: Run all frontend tests**

Run: `cd frontend && npm test`
Expected: all green.

- [ ] **Step 9: Run typecheck**

Run: `cd frontend && npm run typecheck`
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add frontend/components/KnowledgeBaseList.tsx frontend/components/KnowledgeBaseList.test.tsx frontend/components/KnowledgeBaseCreateDialog.tsx frontend/components/KnowledgeBaseCreateDialog.test.tsx frontend/app/(protected)/knowledge-bases/page.tsx
git commit -m "feat(frontend): add knowledge bases list page

/knowledge-bases shows all of the current user's KBs with file counts,
+ New dialog for creation, and a confirm prompt for delete. Empty
state guides the user to the create button.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Knowledge Base Detail Page + Upload + File List

**Files:**
- Create: `frontend/components/FileUploadCard.tsx`
- Create: `frontend/components/FileUploadCard.test.tsx`
- Create: `frontend/components/FileList.tsx`
- Create: `frontend/components/FileList.test.tsx`
- Create: `frontend/app/(protected)/knowledge-bases/[id]/page.tsx`

- [ ] **Step 1: Write failing tests for FileUploadCard**

Create `frontend/components/FileUploadCard.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FileUploadCard } from "./FileUploadCard";

describe("FileUploadCard", () => {
  it("disables Upload until a file is chosen", () => {
    render(<FileUploadCard onUpload={() => Promise.resolve()} />);
    expect(screen.getByRole("button", { name: /upload/i })).toBeDisabled();
  });

  it("calls onUpload with the chosen file", async () => {
    const onUpload = vi.fn().mockResolvedValue(undefined);
    render(<FileUploadCard onUpload={onUpload} />);
    const f = new File(["hi"], "x.txt", { type: "text/plain" });
    const input = screen.getByLabelText(/choose file/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [f] } });
    await userEvent.click(screen.getByRole("button", { name: /upload/i }));
    expect(onUpload).toHaveBeenCalledTimes(1);
    expect(onUpload.mock.calls[0][0]).toBe(f);
  });

  it("shows progress percentage as it changes", async () => {
    let setProgress: ((pct: number) => void) | null = null;
    const onUpload = vi.fn((_file, onProgress) => {
      setProgress = onProgress;
      return new Promise<void>(() => {}); // never resolves so the bar stays
    });
    render(<FileUploadCard onUpload={onUpload as any} />);
    const f = new File(["hi"], "x.txt");
    const input = screen.getByLabelText(/choose file/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [f] } });
    await userEvent.click(screen.getByRole("button", { name: /upload/i }));
    expect(setProgress).not.toBeNull();
    setProgress!(40);
    expect(await screen.findByText("40%")).toBeInTheDocument();
  });

  it("renders error from onUpload", async () => {
    const onUpload = vi.fn().mockRejectedValue(new Error("invalid_extension"));
    render(<FileUploadCard onUpload={onUpload} />);
    const f = new File(["hi"], "x.exe");
    const input = screen.getByLabelText(/choose file/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [f] } });
    await userEvent.click(screen.getByRole("button", { name: /upload/i }));
    expect(
      await screen.findByText("Only TXT, PDF, and CS files are supported"),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement FileUploadCard**

Create `frontend/components/FileUploadCard.tsx`:

```typescript
"use client";

import { useRef, useState, type ChangeEvent } from "react";
import { isAxiosError } from "axios";

const ERROR_FALLBACKS: Record<string, string> = {
  invalid_extension: "Only TXT, PDF, and CS files are supported",
  invalid_content: "File contents do not match the file type",
  file_too_large: "File exceeds the 50 MB limit",
  duplicate_filename:
    "A file with this name already exists. Delete it first to re-upload.",
  kb_not_found: "Knowledge base not found",
};

type Props = {
  onUpload: (file: File, onProgress: (pct: number) => void) => Promise<void>;
};

function extractErrorCode(err: unknown): string | null {
  if (err instanceof Error && err.message in ERROR_FALLBACKS) return err.message;
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}

export function FileUploadCard({ onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    setFile(e.target.files?.[0] ?? null);
    setErrorCode(null);
  }

  async function handleUpload() {
    if (!file) return;
    setErrorCode(null);
    setProgress(0);
    try {
      await onUpload(file, (pct) => setProgress(pct));
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      setErrorCode(extractErrorCode(err) ?? "unknown");
    } finally {
      setProgress(null);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-white p-4">
      <label htmlFor="file-input" className="block text-sm font-medium">
        Choose file (TXT, PDF, CS — max 50 MB)
      </label>
      <input
        id="file-input"
        ref={inputRef}
        type="file"
        accept=".txt,.pdf,.cs"
        onChange={onChange}
        className="mt-2 block w-full text-sm"
      />
      {file ? (
        <div className="mt-2 text-xs text-muted-foreground">
          {file.name} · {Math.round(file.size / 1024)} KB
        </div>
      ) : null}
      {progress !== null ? (
        <div className="mt-3">
          <div className="h-2 w-full rounded-full bg-muted">
            <div
              className="h-2 rounded-full bg-foreground"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-1 text-xs text-muted-foreground">{progress}%</div>
        </div>
      ) : null}
      {errorCode ? (
        <div className="mt-3 text-sm text-red-600" data-testid="upload-error">
          {ERROR_FALLBACKS[errorCode] ?? "Upload failed"}
        </div>
      ) : null}
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={handleUpload}
          disabled={!file || progress !== null}
          className="rounded-md bg-foreground px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Upload
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Run upload card tests**

Run: `cd frontend && npm test -- FileUploadCard.test`
Expected: all green.

- [ ] **Step 4: Write failing tests for FileList**

Create `frontend/components/FileList.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FileList } from "./FileList";

const file = (id: number, filename: string, status = "uploaded") => ({
  id, knowledge_base_id: 1, filename, extension: "txt", size_bytes: 1024,
  status, status_error: null, created_at: "2026-04-26T00:00:00Z",
});

describe("FileList", () => {
  it("renders empty state", () => {
    render(<FileList items={[]} onDelete={() => {}} />);
    expect(screen.getByText(/no files yet/i)).toBeInTheDocument();
  });

  it("renders 'Pending processing' for uploaded status", () => {
    render(<FileList items={[file(1, "a.txt")]} onDelete={() => {}} />);
    expect(screen.getByText("Pending processing")).toBeInTheDocument();
  });

  it("calls onDelete with id when delete clicked", async () => {
    const onDelete = vi.fn();
    render(<FileList items={[file(7, "x.txt")]} onDelete={onDelete} />);
    await userEvent.click(screen.getByRole("button", { name: /delete x.txt/i }));
    expect(onDelete).toHaveBeenCalledWith(7);
  });
});
```

- [ ] **Step 5: Implement FileList**

Create `frontend/components/FileList.tsx`:

```typescript
"use client";

import type { KnowledgeFile } from "../lib/knowledge-bases";

const STATUS_LABEL: Record<string, string> = {
  uploaded: "Pending processing",
  parsing: "Parsing…",
  parsed: "Parsed",
  embedding: "Embedding…",
  indexed: "Indexed",
  failed: "Failed",
};

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type Props = {
  items: KnowledgeFile[];
  onDelete: (id: number) => void;
};

export function FileList({ items, onDelete }: Props) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-white p-8 text-center text-sm text-muted-foreground">
        No files yet. Upload a TXT, PDF, or CS file to get started.
      </div>
    );
  }
  return (
    <ul className="divide-y divide-border rounded-lg border border-border bg-white">
      {items.map((f) => (
        <li key={f.id} className="flex items-center justify-between px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">{f.filename}</div>
            <div className="text-xs text-muted-foreground">
              {f.extension.toUpperCase()} · {humanSize(f.size_bytes)} ·{" "}
              {STATUS_LABEL[f.status] ?? f.status}
            </div>
          </div>
          <button
            type="button"
            onClick={() => onDelete(f.id)}
            aria-label={`Delete ${f.filename}`}
            className="ml-3 rounded-md border border-border px-2 py-1 text-xs text-red-600 hover:bg-red-50"
          >
            Delete
          </button>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 6: Run list tests**

Run: `cd frontend && npm test -- FileList.test`
Expected: all green.

- [ ] **Step 7: Implement the detail page**

Create `frontend/app/(protected)/knowledge-bases/[id]/page.tsx`:

```typescript
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ConfirmDialog } from "../../../../components/ConfirmDialog";
import { FileList } from "../../../../components/FileList";
import { FileUploadCard } from "../../../../components/FileUploadCard";
import {
  deleteFile,
  listFiles,
  uploadFile,
  type KnowledgeFile,
} from "../../../../lib/knowledge-bases";

export default function KnowledgeBaseDetailPage() {
  const params = useParams<{ id: string }>();
  const kbId = Number(params.id);
  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeFile | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      setFiles(await listFiles(kbId));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (Number.isFinite(kbId)) refresh();
  }, [kbId]);

  async function handleUpload(file: File, onProgress: (pct: number) => void) {
    await uploadFile(kbId, file, onProgress);
    await refresh();
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    const id = deleteTarget.id;
    setDeleteTarget(null);
    await deleteFile(kbId, id);
    await refresh();
  }

  return (
    <main className="min-h-screen bg-background p-6 text-foreground">
      <div className="mx-auto max-w-3xl space-y-4">
        <Link
          href="/knowledge-bases"
          className="text-xs text-muted-foreground hover:underline"
        >
          ← Knowledge Bases
        </Link>
        <h1 className="text-xl font-semibold">Knowledge Base #{kbId}</h1>
        <FileUploadCard onUpload={handleUpload} />
        {loading ? (
          <div className="text-sm text-muted-foreground">Loading…</div>
        ) : (
          <FileList
            items={files}
            onDelete={(id) => {
              const target = files.find((f) => f.id === id);
              if (target) setDeleteTarget(target);
            }}
          />
        )}
      </div>
      <ConfirmDialog
        open={deleteTarget !== null}
        title={deleteTarget ? `Delete "${deleteTarget.filename}"?` : ""}
        message="The file will be removed from this knowledge base."
        confirmLabel="Delete"
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </main>
  );
}
```

- [ ] **Step 8: Run all frontend tests**

Run: `cd frontend && npm test`
Expected: all green.

- [ ] **Step 9: Run typecheck**

Run: `cd frontend && npm run typecheck`
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add frontend/components/FileUploadCard.tsx frontend/components/FileUploadCard.test.tsx frontend/components/FileList.tsx frontend/components/FileList.test.tsx "frontend/app/(protected)/knowledge-bases/[id]/page.tsx"
git commit -m "feat(frontend): add knowledge base detail page with upload + file list

/knowledge-bases/[id] hosts the upload card and the file list with
status badges. Confirm dialog gates deletes; FileList maps the
file_status enum to human labels (\"Pending processing\" for uploaded
since A does not yet drive the worker).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Sidebar Navigation Wiring

**Files:**
- Modify: `frontend/app/(protected)/page.tsx`

- [ ] **Step 1: Update sidebar to navigate**

Replace the `Home` component in `frontend/app/(protected)/page.tsx`. The change makes the existing "Knowledge" sidebar item navigate to `/knowledge-bases`:

```typescript
"use client";

import { FileText, LogOut, MessageSquare, Presentation, Search } from "lucide-react";
import { useRouter } from "next/navigation";

import { useAuthStore } from "../../lib/auth-store";

const navItems: { label: string; icon: typeof MessageSquare; href?: string }[] = [
  { label: "Chat", icon: MessageSquare },
  { label: "Knowledge", icon: Search, href: "/knowledge-bases" },
  { label: "Documents", icon: FileText },
  { label: "Slides", icon: Presentation },
];

export default function Home() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const clearSession = useAuthStore((s) => s.clearSession);

  function handleLogout() {
    clearSession();
    router.push("/login");
  }

  return (
    <main className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-64 border-r border-border bg-white/80 px-4 py-5 md:block">
        <div className="mb-6 text-lg font-semibold">KnowledgeDeck</div>
        <nav className="space-y-1">
          {navItems.map((item) => (
            <button
              className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              key={item.label}
              type="button"
              onClick={() => {
                if (item.href) router.push(item.href);
              }}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </button>
          ))}
        </nav>
        <div className="mt-6 border-t border-border pt-4 text-xs text-muted-foreground">
          <div className="mb-2 truncate" title={user?.username}>{user?.username ?? ""}</div>
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 rounded-md px-2 py-1 hover:bg-muted hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </aside>
      <section className="flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-border bg-white/80 px-4">
          <div className="text-sm font-medium">Chat</div>
          <div className="text-xs text-muted-foreground">Model: Gemma 4 E4B</div>
        </header>
        <div className="flex flex-1 items-center justify-center px-4">
          <div className="w-full max-w-3xl">
            <h1 className="mb-3 text-2xl font-semibold">Ask KnowledgeDeck</h1>
            <div className="rounded-lg border border-border bg-white p-3 shadow-sm">
              <textarea
                className="min-h-28 w-full resize-none bg-transparent text-sm outline-none"
                placeholder="Ask a question or describe the presentation you want to create..."
              />
              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs text-muted-foreground">RAG ready scaffold</span>
                <button className="rounded-md bg-foreground px-3 py-2 text-sm text-white" type="button">
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
```

- [ ] **Step 2: Run frontend tests + typecheck**

Run: `cd frontend && npm test && npm run typecheck`
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add "frontend/app/(protected)/page.tsx"
git commit -m "feat(frontend): wire chat sidebar 'Knowledge' item to /knowledge-bases

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Manual End-to-End Verification

**Files:** None (verification only).

This task is run by the user. It verifies the full stack on the SSH dev box at `192.168.1.102` with the user logged into the browser.

- [ ] **Step 1: Bring up the stack**

Run: `docker compose up postgres redis qdrant minio backend frontend`
Wait for `Application startup complete` from backend.

- [ ] **Step 2: Verify backend bucket creation**

In another terminal:

```bash
docker compose logs minio | grep -i bucket
docker compose exec minio mc alias set local http://localhost:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"
docker compose exec minio mc ls local/knowledgedeck
```

Expected: bucket exists (output may be empty since no files uploaded yet — that's fine, the goal is "bucket present").

- [ ] **Step 3: Browser flow at http://192.168.1.102:3000**

1. Log in as `admin` / `admin`.
2. Click "Knowledge" in the sidebar — `/knowledge-bases` loads with empty state.
3. Click "+ New", enter name `Smoke Test`, description `phase 2 sub-A`, click Create. Row appears with `0 files`.
4. Click the row — `/knowledge-bases/<id>` opens.
5. Use a small TXT file (`echo hello > /tmp/sample.txt`); pick it; click Upload. Progress bar runs; file appears with status `Pending processing`.
6. Try to upload the same `sample.txt` again — error message "A file with this name already exists. Delete it first to re-upload." appears.
7. Try to upload a `.exe` file — error "Only TXT, PDF, and CS files are supported" appears.
8. Click Delete on the file → confirm → file disappears.
9. Click "← Knowledge Bases" → back on list page; the KB still shows `0 files` (deleted file no longer counted).
10. Click Delete on the KB → confirm → KB disappears.

- [ ] **Step 4: Verify soft-delete in DB**

Run:

```bash
docker compose exec postgres psql -U knowledgedeck -d knowledgedeck \
  -c "SELECT id, name, deleted_at FROM knowledge_bases ORDER BY id;"
docker compose exec postgres psql -U knowledgedeck -d knowledgedeck \
  -c "SELECT id, filename, deleted_at FROM files ORDER BY id;"
```

Expected: rows still exist with `deleted_at` populated (proves soft delete, not hard delete).

- [ ] **Step 5: Verify MinIO object still present**

Run: `docker compose exec minio mc ls --recursive local/knowledgedeck`
Expected: `kb/<kb_id>/files/<file_id>/original.txt` is still listed (MinIO not cleaned up — by design; future cleanup job's responsibility).

- [ ] **Step 6: Tear down + final commit**

If everything passes:

```bash
docker compose down
git status   # should be clean
```

Report results to the user. If any step fails, file a follow-up issue rather than silently fixing — the spec said "Sub-project A is upload + storage only".

---

## Self-Review

This section is for the planner to verify before handoff. Already executed:

1. **Spec coverage:**
   - `knowledge_bases` / `files` tables with soft delete → Task 2.
   - 6 endpoints (POST/GET/DELETE knowledge-bases + POST/GET/DELETE files) → Tasks 4, 5, 6.
   - MinIO key layout `kb/{kb_id}/files/{file_id}/original.{ext}` → Task 5 (computed after `flush()` for `id`).
   - `minio-py` wrapped in `asyncio.to_thread` → Task 3.
   - Format validation (extension + PDF magic + TXT/CS UTF-8/no-NUL) → Task 5 (`file_service.validate_extension` + `validate_content`).
   - 50 MiB cap → Task 5 (`stream_into_buffer` raises before exceeding).
   - 409 on duplicate filename → Task 5 endpoint check + DB partial unique index from Task 2.
   - testcontainers MinIO + Postgres patterns → Task 3 (MinIO fixture) + reused Postgres from existing conftest.
   - Frontend `/knowledge-bases` list page → Task 9.
   - Frontend `/knowledge-bases/[id]` detail page → Task 10.
   - Components in `frontend/components/` (KnowledgeBaseList, KnowledgeBaseCreateDialog, FileUploadCard, FileList, ConfirmDialog) → Tasks 8, 9, 10.
   - ERROR_FALLBACKS pattern reused → Tasks 9, 10.
   - Sidebar link → Task 11.
   - Manual E2E in browser at 192.168.1.102 → Task 12.
2. **Placeholder scan:** None.
3. **Type consistency:** `KnowledgeBase` / `KnowledgeFile` / `KnowledgeBaseCreated` types declared in `lib/knowledge-bases.ts` (Task 7) match the backend response shapes from Tasks 4–6. `file_status` enum string values match between backend Python enum, Alembic migration, and frontend `STATUS_LABEL`. Method names (`listKnowledgeBases`, `createKnowledgeBase`, `deleteKnowledgeBase`, `listFiles`, `uploadFile`, `deleteFile`) consistent across client, tests, and pages.
4. **Spec → plan deviations called out:** "Reuses auth's existing shape" was a spec contradiction; the plan adopts the *actual* existing shape `{"detail": "code_string"}`. Documented in the "Spec ↔ Existing-Pattern Reconciliation" section above.
