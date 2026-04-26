# KnowledgeDeck Auth Implementation Plan (MVP — Minimal)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the minimum-viable auth flow per [docs/superpowers/specs/2026-04-25-knowledgedeck-auth-design.md](../specs/2026-04-25-knowledgedeck-auth-design.md): admin-inserted username + plaintext password, opaque `u_<id>` bearer token, login + me endpoints, CLI for user creation, lifespan-based first-user seed, frontend login page with localStorage-backed Zustand store.

**Architecture:** SQLAlchemy 2.0 async + psycopg 3 + Alembic for the single-table `users` schema; testcontainers Postgres for backend tests; FastAPI with a `lifespan` context for startup seeding; Next.js 15 client components with axios + Zustand for the frontend.

**Tech Stack:** SQLAlchemy 2.0 async, psycopg 3, Alembic, Typer, FastAPI lifespan, testcontainers-python (PostgreSQL); Next.js 15, Zustand, axios, vitest + @testing-library/react.

---

## Scope

This plan implements the entire auth design spec. It does not implement Phase 4 hardening (hashing, JWT, refresh, audit, rate limiting, admin role, logout endpoint), Phase 4 admin web UI, or the broader i18n architecture (only the error code contract is fixed here).

## File Structure

**Backend:**

- Modify `backend/pyproject.toml`: add `sqlalchemy>=2.0.32`, `psycopg[binary]>=3.2`, `alembic>=1.13`, `typer>=0.12`; dev: `testcontainers[postgresql]>=4.8`. Add `[tool.pytest.ini_options]` block with `asyncio_mode = "auto"`.
- Modify `backend/app/core/config.py`: add `database_url`, `initial_user_username`, `initial_user_password`. Remove the existing `jwt_secret_key`, `jwt_algorithm`, `jwt_access_token_minutes` fields (no JWT in MVP).
- Modify `backend/tests/test_config.py`: assert new defaults.
- Create `backend/app/db/__init__.py`, `backend/app/db/base.py`: SQLAlchemy declarative `Base`, lazy async engine, `async_session_factory`, `get_db` dependency.
- Create `backend/app/db/models.py`: `User` only.
- Create `backend/tests/test_models.py`: import-only smoke tests on `User` table metadata.
- Create `backend/alembic.ini`, `backend/app/db/migrations/env.py`, `backend/app/db/migrations/script.py.mako`, `backend/app/db/migrations/__init__.py`, `backend/app/db/migrations/versions/__init__.py`, `backend/app/db/migrations/versions/0001_initial.py`: Alembic config and the first migration creating the `users` table.
- Create `backend/tests/conftest.py`: testcontainers Postgres fixture, alembic upgrade-on-session, session-scoped engine, autouse monkeypatch of `app.db.base._engine` / `_session_factory`, per-test TRUNCATE.
- Create `backend/tests/test_migration.py`: smoke test that `alembic upgrade head` produces the `users` table.
- Create `backend/app/services/auth_service.py`: `authenticate(session, username, password) -> User | None`.
- Create `backend/tests/test_auth_service.py`.
- Create `backend/app/api/deps.py`: `get_current_user`.
- Create `backend/tests/test_deps.py`.
- Create `backend/app/api/auth.py`: `/auth/login`, `/auth/me` router.
- Create `backend/tests/test_auth_login.py`, `backend/tests/test_auth_me.py`.
- Modify `backend/app/main.py`: register auth router, wire FastAPI `lifespan` running the seed.
- Create `backend/app/startup.py`: `seed_initial_user` lifespan helper.
- Create `backend/tests/test_seed_user.py`.
- Create `backend/app/cli.py`: Typer app with the single `create-user` command.
- Create `backend/tests/test_cli.py`.
- Modify `backend/Dockerfile`: copy `alembic.ini`, change CMD to `sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080"`.
- Modify `.env.example`: replace JWT vars with `INITIAL_USER_USERNAME`, `INITIAL_USER_PASSWORD`.

**Frontend:**

- Modify `frontend/package.json`: add `axios>=1.7`, `zustand>=5.0`; dev: `vitest`, `@vitejs/plugin-react`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `axios-mock-adapter`.
- Create `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`.
- Create `frontend/lib/auth-store.ts`, `frontend/lib/auth-store.test.ts`.
- Create `frontend/lib/api.ts`, `frontend/lib/api.test.ts`.
- Create `frontend/components/AuthGuard.tsx`, `frontend/components/AuthGuard.test.tsx`.
- Create `frontend/app/login/page.tsx`, `frontend/app/login/page.test.tsx`.
- Create `frontend/app/(protected)/layout.tsx`.
- Move `frontend/app/page.tsx` → `frontend/app/(protected)/page.tsx`; add a logout button that calls `clearSession()` and routes to `/login`.

---

## Conventions Used Below

- Backend tests run with system `python3` (3.10).
- Frontend tooling uses Node 24 at `/homepool2/tobyleung/actions-runner/externals.2.330.0/node24/bin/node`; npm cli at the same prefix's `lib/node_modules/npm/bin/npm-cli.js`. Each frontend command in this plan abbreviates the helper as `NPM`.
- All commits land directly on the `dev` branch in the main working tree at `/homepool2/minkuanchen/KnowledgeDeckAIPlatform/`. No feature branch, no worktree (per project owner preference for this iteration).
- Every task ends in a commit. Test commands return non-zero only on failure.

---

### Task 1: Backend Settings, Deps, ORM, and Migration

This task bundles the four foundational concerns (deps, settings, ORM, Alembic + test fixture) into one bigger commit because the new MVP auth schema is so small (one table, four columns) that splitting them adds more cognitive overhead than it removes.

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/test_config.py`
- Modify: `.env.example`
- Create: `backend/app/db/__init__.py`, `backend/app/db/base.py`, `backend/app/db/models.py`
- Create: `backend/tests/test_models.py`
- Create: `backend/alembic.ini`
- Create: `backend/app/db/migrations/__init__.py`, `backend/app/db/migrations/env.py`, `backend/app/db/migrations/script.py.mako`
- Create: `backend/app/db/migrations/versions/__init__.py`, `backend/app/db/migrations/versions/0001_initial.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_migration.py`

- [ ] **Step 1: Update `backend/pyproject.toml`**

Replace the `[project]` and `[project.optional-dependencies]` blocks (and add the `[tool.pytest.ini_options]` block) so the file becomes:

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
    "psycopg[binary]>=3.2.0",
    "pydantic-settings>=2.4.0",
    "sqlalchemy>=2.0.32",
    "typer>=0.12.0",
    "uvicorn[standard]>=0.30.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "testcontainers[postgresql]>=4.8.0",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
asyncio_mode = "auto"
```

Notable removals vs scaffold pyproject: `argon2-cffi`, `pyjwt`, `email-validator` are intentionally absent — the MVP needs none of them.

- [ ] **Step 2: Update `backend/app/core/config.py`**

Replace the file with:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "KnowledgeDeck"
    environment: str = "local"
    api_prefix: str = "/api"

    database_url: str = (
        "postgresql+psycopg://knowledgedeck:change-me@knowledgedeck_postgres:5432/knowledgedeck"
    )

    initial_user_username: str = ""
    initial_user_password: str = ""

    llm_base_url: str = "http://knowledgedeck_vllm_chat:8000/v1"
    llm_api_key: str = "local-dev-key"
    llm_model: str = "google/gemma-4-E4B-it"

    embedding_base_url: str = "http://knowledgedeck_vllm_embedding:8001/v1"
    embedding_api_key: str = "local-dev-key"
    embedding_model: str = "BAAI/bge-m3"

    gpu_device: str = "0"
    vllm_chat_gpu_memory_utilization: float = 0.70
    vllm_chat_max_model_len: int = 16384
    vllm_embedding_gpu_memory_utilization: float = 0.22
    vllm_embedding_max_model_len: int = 8192


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

(All `jwt_*` fields and the `pydantic.Field` import are removed.)

- [ ] **Step 3: Update `backend/tests/test_config.py`**

Replace the file with:

```python
from app.core.config import Settings


def test_settings_defaults_match_local_development() -> None:
    settings = Settings()

    assert settings.app_name == "KnowledgeDeck"
    assert settings.environment == "local"
    assert settings.llm_base_url == "http://knowledgedeck_vllm_chat:8000/v1"
    assert settings.llm_model == "google/gemma-4-E4B-it"
    assert settings.embedding_base_url == "http://knowledgedeck_vllm_embedding:8001/v1"
    assert settings.embedding_model == "BAAI/bge-m3"
    assert settings.gpu_device == "0"
    assert settings.database_url == (
        "postgresql+psycopg://knowledgedeck:change-me@knowledgedeck_postgres:5432/knowledgedeck"
    )
    assert settings.initial_user_username == ""
    assert settings.initial_user_password == ""


def test_settings_accept_endpoint_overrides() -> None:
    settings = Settings(
        llm_base_url="https://models.example.test/v1",
        llm_api_key="test-key",
        llm_model="custom-chat",
        embedding_base_url="https://embeddings.example.test/v1",
        embedding_api_key="embedding-key",
        embedding_model="custom-embedding",
    )

    assert settings.llm_base_url == "https://models.example.test/v1"
    assert settings.llm_api_key == "test-key"
    assert settings.llm_model == "custom-chat"
    assert settings.embedding_base_url == "https://embeddings.example.test/v1"
    assert settings.embedding_api_key == "embedding-key"
    assert settings.embedding_model == "custom-embedding"


def test_settings_accept_initial_user_overrides() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        initial_user_username="admin",
        initial_user_password="admin-password",
    )

    assert settings.database_url == "postgresql+psycopg://test:test@localhost:5432/test"
    assert settings.initial_user_username == "admin"
    assert settings.initial_user_password == "admin-password"
```

- [ ] **Step 4: Update `.env.example`**

Replace the JWT-related block with:

```env
INITIAL_USER_USERNAME=admin
INITIAL_USER_PASSWORD=admin
```

(Remove `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_MINUTES` lines entirely.)

- [ ] **Step 5: Install backend deps**

```bash
cd backend
python3 -m pip install --user --upgrade 'sqlalchemy>=2.0.32' 'psycopg[binary]>=3.2.0' 'alembic>=1.13.0' 'typer>=0.12.0' 'testcontainers[postgresql]>=4.8.0'
```

Expected: pip prints success.

- [ ] **Step 6: Create the SQLAlchemy base + engine**

Create `backend/app/db/__init__.py`:

```python
from app.db.base import Base, async_session_factory, get_db, get_engine

__all__ = ["Base", "async_session_factory", "get_db", "get_engine"]
```

Create `backend/app/db/base.py`:

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, future=True, pool_pre_ping=True)
    return _engine


def async_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an AsyncSession scoped to a single request."""
    async with async_session_factory()() as session:
        yield session
```

- [ ] **Step 7: Create the User ORM**

Create `backend/app/db/models.py`:

```python
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 8: Add a metadata smoke test**

Create `backend/tests/test_models.py`:

```python
from app.db.models import User


def test_user_table_metadata() -> None:
    assert User.__tablename__ == "users"
    columns = {c.name for c in User.__table__.columns}
    assert columns == {"id", "username", "password", "created_at"}
```

- [ ] **Step 9: Add Alembic configuration**

Create `backend/alembic.ini`:

```ini
[alembic]
script_location = app/db/migrations
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = driver://user:pass@localhost/db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create empty `backend/app/db/migrations/__init__.py` and `backend/app/db/migrations/versions/__init__.py`.

Create `backend/app/db/migrations/script.py.mako`:

```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create `backend/app/db/migrations/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401  ensure model imports register metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if not config.get_main_option("sqlalchemy.url") or config.get_main_option(
    "sqlalchemy.url"
).startswith("driver://"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 10: Write the initial migration**

Create `backend/app/db/migrations/versions/0001_initial.py`:

```python
"""initial users table

Revision ID: 0001
Revises:
Create Date: 2026-04-25 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("username", sa.Text, nullable=False, unique=True),
        sa.Column("password", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("users")
```

- [ ] **Step 11: Add the testcontainers conftest**

Create `backend/tests/conftest.py`:

```python
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

BACKEND_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def postgres_url() -> AsyncIterator[str]:
    with PostgresContainer("postgres:16-alpine") as container:
        sync_url = container.get_connection_url()
        async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
        if async_url.startswith("postgresql://"):
            async_url = async_url.replace("postgresql://", "postgresql+psycopg://", 1)
        yield async_url


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(postgres_url: str) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "app" / "db" / "migrations"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(config, "head")


@pytest_asyncio.fixture(scope="session")
async def shared_engine(postgres_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(postgres_url, future=True, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
def _patch_app_db(monkeypatch, shared_engine: AsyncEngine) -> None:
    """Make app.db.base.get_engine() / async_session_factory() share the test engine."""
    from app.db import base as db_base

    factory = async_sessionmaker(shared_engine, expire_on_commit=False)
    monkeypatch.setattr(db_base, "_engine", shared_engine, raising=False)
    monkeypatch.setattr(db_base, "_session_factory", factory, raising=False)


@pytest_asyncio.fixture()
async def db_session(shared_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Per-test clean state via TRUNCATE; tests may freely commit."""
    factory = async_sessionmaker(shared_engine, expire_on_commit=False)
    async with factory() as setup:
        await setup.execute(text("TRUNCATE TABLE users RESTART IDENTITY"))
        await setup.commit()

    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
```

(No CASCADE on TRUNCATE because `login_logs` does not exist in this MVP.)

- [ ] **Step 12: Add the migration smoke test**

Create `backend/tests/test_migration.py`:

```python
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
```

- [ ] **Step 13: Run the full test suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: all tests pass (3 config + 2 health + 2 model_clients + 1 model + 1 migration = 9 tests).

- [ ] **Step 14: Commit**

```bash
git add backend/pyproject.toml backend/app/core/config.py backend/tests/test_config.py .env.example backend/app/db backend/tests/test_models.py backend/alembic.ini backend/app/db/migrations backend/tests/conftest.py backend/tests/test_migration.py
git commit -m "feat: add minimal-mvp settings, ORM, and alembic for auth"
```

---

### Task 2: Auth Service (`authenticate`)

**Files:**
- Create: `backend/app/services/auth_service.py`
- Modify: `backend/app/services/__init__.py`
- Create: `backend/tests/test_auth_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_auth_service.py`:

```python
import pytest

from app.db.models import User
from app.services.auth_service import authenticate


@pytest.fixture()
async def seeded_user(db_session) -> User:
    user = User(username="alice", password="hunter2")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_authenticate_success(db_session, seeded_user: User) -> None:
    user = await authenticate(db_session, "alice", "hunter2")
    assert user is not None
    assert user.id == seeded_user.id


@pytest.mark.asyncio
async def test_authenticate_wrong_password(db_session, seeded_user: User) -> None:
    assert await authenticate(db_session, "alice", "WRONG") is None


@pytest.mark.asyncio
async def test_authenticate_unknown_username(db_session) -> None:
    assert await authenticate(db_session, "ghost", "anything") is None


@pytest.mark.asyncio
async def test_authenticate_is_case_sensitive(db_session, seeded_user: User) -> None:
    assert await authenticate(db_session, "Alice", "hunter2") is None
```

- [ ] **Step 2: Run to confirm RED**

```bash
cd backend
python3 -m pytest tests/test_auth_service.py -v
```

Expected: ModuleNotFoundError on `app.services.auth_service`.

- [ ] **Step 3: Implement the auth service**

Create `backend/app/services/auth_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def authenticate(session: AsyncSession, username: str, password: str) -> User | None:
    user = await session.scalar(select(User).where(User.username == username))
    if user is None:
        return None
    if user.password != password:
        return None
    return user
```

Update `backend/app/services/__init__.py` to add the new export (preserve existing model_clients exports):

```python
from app.services.auth_service import authenticate
from app.services.model_clients import ChatModelClient, EmbeddingClient

__all__ = ["ChatModelClient", "EmbeddingClient", "authenticate"]
```

- [ ] **Step 4: Run the auth service tests**

```bash
cd backend
python3 -m pytest tests/test_auth_service.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Run the full backend suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: 13 tests pass (9 from Task 1 + 4 new).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/auth_service.py backend/app/services/__init__.py backend/tests/test_auth_service.py
git commit -m "feat: add minimal auth service with plaintext password compare"
```

---

### Task 3: Auth Dependency (`get_current_user`)

**Files:**
- Create: `backend/app/api/deps.py`
- Create: `backend/tests/test_deps.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_deps.py`:

```python
import pytest
from fastapi import HTTPException

from app.api.deps import get_current_user
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
```

- [ ] **Step 2: Confirm RED**

```bash
cd backend
python3 -m pytest tests/test_deps.py -v
```

Expected: ModuleNotFoundError on `app.api.deps`.

- [ ] **Step 3: Implement the dependency**

Create `backend/app/api/deps.py`:

```python
import re
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import User

# Bounded to PostgreSQL BIGINT range (max 9_223_372_036_854_775_807, 19 digits)
# and rejects leading zeros / id=0 so over-long values surface as 401, not 500.
_TOKEN_RE = re.compile(r"^u_([1-9]\d{0,18})$")


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    token = authorization.split(" ", 1)[1]
    match = _TOKEN_RE.match(token)
    if not match:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    user_id = int(match.group(1))
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    return user
```

- [ ] **Step 4: Run the dep tests**

```bash
cd backend
python3 -m pytest tests/test_deps.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Run the full backend suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: 18 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/deps.py backend/tests/test_deps.py
git commit -m "feat: add get_current_user dependency that parses u_<id> tokens"
```

---

### Task 4: Auth API Endpoints

**Files:**
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_auth_login.py`
- Create: `backend/tests/test_auth_me.py`

- [ ] **Step 1: Write failing endpoint tests**

Create `backend/tests/test_auth_login.py`:

```python
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
```

Create `backend/tests/test_auth_me.py`:

```python
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
```

- [ ] **Step 2: Confirm RED**

```bash
cd backend
python3 -m pytest tests/test_auth_login.py tests/test_auth_me.py -v
```

Expected: ModuleNotFoundError on `app.api.auth` (because `app.main.create_app` is patched in Step 4 to import it).

- [ ] **Step 3: Implement the auth router**

Create `backend/app/api/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.db.models import User
from app.services.auth_service import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserSummary(BaseModel):
    id: int
    username: str


class LoginResponse(BaseModel):
    token: str
    user: UserSummary


class MeResponse(BaseModel):
    id: int
    username: str
    created_at: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)) -> LoginResponse:
    user = await authenticate(session, body.username, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    return LoginResponse(
        token=f"u_{user.id}",
        user=UserSummary(id=user.id, username=user.username),
    )


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=user.id,
        username=user.username,
        created_at=user.created_at.isoformat(),
    )
```

- [ ] **Step 4: Wire the router into the FastAPI app**

Replace `backend/app/main.py` with:

```python
from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="KnowledgeDeck API", version="0.1.0")
    app.include_router(health_router)
    app.include_router(auth_router)
    return app


app = create_app()
```

(The lifespan that runs the seed is added in Task 5; keep `create_app` minimal here.)

- [ ] **Step 5: Run the endpoint tests**

```bash
cd backend
python3 -m pytest tests/test_auth_login.py tests/test_auth_me.py -v
```

Expected: 7 tests pass.

- [ ] **Step 6: Run the full backend suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: 25 tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/auth.py backend/app/main.py backend/tests/test_auth_login.py backend/tests/test_auth_me.py
git commit -m "feat: add /auth/login and /auth/me endpoints"
```

---

### Task 5: First-User Seed Lifespan Hook

**Files:**
- Create: `backend/app/startup.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_seed_user.py`

- [ ] **Step 1: Write failing seed tests**

Create `backend/tests/test_seed_user.py`:

```python
import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import User
from app.startup import seed_initial_user


@pytest.mark.asyncio
async def test_seed_creates_user_when_username_does_not_exist(db_session) -> None:
    settings = Settings(initial_user_username="seed-user", initial_user_password="seed-pwd")
    await seed_initial_user(db_session, settings=settings)
    await db_session.commit()
    user = await db_session.scalar(select(User).where(User.username == "seed-user"))
    assert user is not None
    assert user.password == "seed-pwd"


@pytest.mark.asyncio
async def test_seed_skips_when_username_already_exists(db_session) -> None:
    db_session.add(User(username="seed-user", password="original"))
    await db_session.commit()

    settings = Settings(initial_user_username="seed-user", initial_user_password="different")
    await seed_initial_user(db_session, settings=settings)
    await db_session.commit()

    rows = (await db_session.scalars(select(User).where(User.username == "seed-user"))).all()
    assert len(rows) == 1
    assert rows[0].password == "original"  # idempotent: not overwritten


@pytest.mark.asyncio
async def test_seed_no_op_when_username_unset(db_session) -> None:
    settings = Settings(initial_user_username="", initial_user_password="anything")
    await seed_initial_user(db_session, settings=settings)
    await db_session.commit()
    rows = (await db_session.scalars(select(User))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_seed_no_op_when_password_unset(db_session) -> None:
    settings = Settings(initial_user_username="alice", initial_user_password="")
    await seed_initial_user(db_session, settings=settings)
    await db_session.commit()
    rows = (await db_session.scalars(select(User))).all()
    assert rows == []
```

- [ ] **Step 2: Confirm RED**

```bash
cd backend
python3 -m pytest tests/test_seed_user.py -v
```

Expected: ModuleNotFoundError on `app.startup`.

- [ ] **Step 3: Implement the seed**

Create `backend/app/startup.py`:

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.base import async_session_factory
from app.db.models import User

logger = logging.getLogger(__name__)


async def seed_initial_user(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
) -> None:
    cfg = settings or get_settings()
    if not cfg.initial_user_username or not cfg.initial_user_password:
        return
    existing = await session.scalar(select(User).where(User.username == cfg.initial_user_username))
    if existing is not None:
        logger.info("seed_skipped existing_user=%s", cfg.initial_user_username)
        return
    session.add(User(username=cfg.initial_user_username, password=cfg.initial_user_password))
    await session.flush()
    logger.info("seed_created user=%s", cfg.initial_user_username)


@asynccontextmanager
async def lifespan(app: FastAPI):
    factory = async_session_factory()
    async with factory() as session:
        await seed_initial_user(session)
        await session.commit()
    yield
```

- [ ] **Step 4: Wire the lifespan into the FastAPI app**

Replace `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.startup import lifespan


def create_app() -> FastAPI:
    app = FastAPI(title="KnowledgeDeck API", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(auth_router)
    return app


app = create_app()
```

- [ ] **Step 5: Run the seed tests**

```bash
cd backend
python3 -m pytest tests/test_seed_user.py -v
```

Expected: 4 tests pass.

- [ ] **Step 6: Run the full backend suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: 29 tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/startup.py backend/app/main.py backend/tests/test_seed_user.py
git commit -m "feat: add lifespan hook seeding initial user from env"
```

---

### Task 6: CLI Tool + Backend Container Entrypoint

**Files:**
- Create: `backend/app/cli.py`
- Create: `backend/tests/test_cli.py`
- Modify: `backend/Dockerfile`

- [ ] **Step 1: Write failing CLI tests**

Create `backend/tests/test_cli.py`:

```python
import asyncio

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from app.cli import app as cli_app
from app.db.base import async_session_factory
from app.db.models import User


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _fetch_user(username: str) -> User | None:
    async def _q() -> User | None:
        async with async_session_factory()() as session:
            return await session.scalar(select(User).where(User.username == username))

    return asyncio.run(_q())


def test_create_user_inserts_row(runner: CliRunner) -> None:
    result = runner.invoke(cli_app, ["create-user", "alice", "--password", "hunter2"])
    assert result.exit_code == 0, result.output
    user = _fetch_user("alice")
    assert user is not None
    assert user.password == "hunter2"


def test_create_user_rejects_existing_username(runner: CliRunner) -> None:
    first = runner.invoke(cli_app, ["create-user", "bob", "--password", "pwd"])
    assert first.exit_code == 0

    duplicate = runner.invoke(cli_app, ["create-user", "bob", "--password", "different"])
    assert duplicate.exit_code != 0
    assert "already exists" in duplicate.output.lower()
```

- [ ] **Step 2: Confirm RED**

```bash
cd backend
python3 -m pytest tests/test_cli.py -v
```

Expected: ModuleNotFoundError on `app.cli`.

- [ ] **Step 3: Implement the CLI**

Create `backend/app/cli.py`:

```python
import asyncio
from typing import Annotated

import typer
from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models import User

app = typer.Typer(help="KnowledgeDeck admin CLI", no_args_is_help=True)


async def _create_user(username: str, password: str) -> None:
    async with async_session_factory()() as session:
        existing = await session.scalar(select(User).where(User.username == username))
        if existing is not None:
            raise typer.BadParameter(f"user already exists: {username}")
        session.add(User(username=username, password=password))
        await session.commit()


@app.command("create-user")
def create_user(
    username: str,
    password: Annotated[
        str,
        typer.Option(
            prompt=True,
            hide_input=True,
            confirmation_prompt=True,
            help="Password for the new user. Will be prompted if omitted.",
        ),
    ],
) -> None:
    asyncio.run(_create_user(username, password))
    typer.echo(f"created user: {username}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run the CLI tests**

```bash
cd backend
python3 -m pytest tests/test_cli.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Update the backend Dockerfile**

Replace `backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"

COPY app ./app
COPY alembic.ini ./alembic.ini

EXPOSE 8080

# `exec` makes uvicorn replace the wrapping `sh` as PID 1 so SIGTERM from
# `docker stop` reaches uvicorn directly instead of being swallowed by dash.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8080"]
```

- [ ] **Step 6: Validate Docker Compose still renders**

```bash
cp .env.example .env
docker compose --env-file .env.example config >/dev/null && echo "compose OK"
docker compose --env-file .env.example --profile gpu config >/dev/null && echo "compose gpu OK"
rm .env
```

Expected: both `compose OK` and `compose gpu OK`.

- [ ] **Step 7: Run the full backend suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: 31 tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/cli.py backend/tests/test_cli.py backend/Dockerfile
git commit -m "feat: add create-user CLI and migration entrypoint"
```

---

### Task 7: Frontend Test Setup, Auth Store, and Axios Instance

This task bundles three small frontend foundations because they all need to land before any UI code can be tested. Splitting them produces three nearly empty commits.

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`
- Create: `frontend/lib/auth-store.ts`, `frontend/lib/auth-store.test.ts`
- Create: `frontend/lib/api.ts`, `frontend/lib/api.test.ts`

For the rest of the frontend tasks, run all `npm` commands as:

```bash
NODE_DIR=/homepool2/tobyleung/actions-runner/externals.2.330.0/node24/bin
NODE=$NODE_DIR/node
NPM="$NODE $NODE_DIR/../lib/node_modules/npm/bin/npm-cli.js"
PATH="$NODE_DIR:$PATH"
```

- [ ] **Step 1: Update `frontend/package.json`**

Replace with:

```json
{
  "name": "knowledgedeck-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev --hostname 0.0.0.0",
    "build": "next build",
    "lint": "next lint",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@types/node": "^22.7.4",
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.1",
    "autoprefixer": "^10.4.20",
    "axios": "^1.7.7",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.1",
    "lucide-react": "^0.468.0",
    "next": "^15.0.0",
    "postcss": "^8.4.47",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "tailwind-merge": "^2.5.4",
    "tailwindcss": "^3.4.14",
    "typescript": "^5.6.3",
    "zustand": "^5.0.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@vitejs/plugin-react": "^4.3.3",
    "axios-mock-adapter": "^2.1.0",
    "jsdom": "^25.0.1",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 2: Add vitest config**

Create `frontend/vitest.config.ts`:

```typescript
import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
    include: ["**/*.test.{ts,tsx}"],
  },
});
```

Create `frontend/vitest.setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
```

- [ ] **Step 3: Install deps**

```bash
cd frontend
$NPM install
```

- [ ] **Step 4: Auth store tests + impl**

Create `frontend/lib/auth-store.test.ts`:

```typescript
import { beforeEach, describe, expect, it } from "vitest";

import { useAuthStore } from "./auth-store";

describe("auth store", () => {
  beforeEach(() => {
    useAuthStore.getState().clearSession();
    localStorage.clear();
  });

  it("starts empty", () => {
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("setSession populates token and user", () => {
    useAuthStore.getState().setSession("u_7", { id: 7, username: "alice" });
    expect(useAuthStore.getState().token).toBe("u_7");
    expect(useAuthStore.getState().user).toEqual({ id: 7, username: "alice" });
  });

  it("clearSession resets state", () => {
    useAuthStore.getState().setSession("u_7", { id: 7, username: "alice" });
    useAuthStore.getState().clearSession();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("persists token to localStorage under knowledgedeck-auth", () => {
    useAuthStore.getState().setSession("u_42", { id: 42, username: "carol" });
    const raw = localStorage.getItem("knowledgedeck-auth");
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!).state.token).toBe("u_42");
  });
});
```

Create `frontend/lib/auth-store.ts`:

```typescript
"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type AuthUser = { id: number; username: string };

export type AuthState = {
  token: string | null;
  user: AuthUser | null;
  setSession: (token: string, user: AuthUser) => void;
  clearSession: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setSession: (token, user) => set({ token, user }),
      clearSession: () => set({ token: null, user: null }),
    }),
    {
      name: "knowledgedeck-auth",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
```

- [ ] **Step 5: Axios instance tests + impl**

Create `frontend/lib/api.test.ts`:

```typescript
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./api";
import { useAuthStore } from "./auth-store";

describe("api axios instance", () => {
  let mock: MockAdapter;

  beforeEach(() => {
    mock = new MockAdapter(api);
    useAuthStore.getState().clearSession();
    localStorage.clear();
  });

  afterEach(() => {
    mock.restore();
    vi.unstubAllGlobals();
  });

  it("attaches Bearer header when a token is set", async () => {
    useAuthStore.getState().setSession("u_7", { id: 7, username: "alice" });
    mock.onGet("/echo").reply((config) => [200, { auth: config.headers?.Authorization ?? null }]);
    const res = await api.get("/echo");
    expect(res.data).toEqual({ auth: "Bearer u_7" });
  });

  it("omits Authorization header when no token is set", async () => {
    mock.onGet("/echo").reply((config) => [200, { auth: config.headers?.Authorization ?? null }]);
    const res = await api.get("/echo");
    expect(res.data).toEqual({ auth: null });
  });

  it("clears session and redirects on 401", async () => {
    useAuthStore.getState().setSession("u_7", { id: 7, username: "alice" });
    mock.onGet("/protected").reply(401, { detail: "invalid_token" });
    const replaceMock = vi.fn();
    vi.stubGlobal("location", { ...window.location, pathname: "/dashboard", replace: replaceMock });

    await expect(api.get("/protected")).rejects.toThrow();
    expect(useAuthStore.getState().token).toBeNull();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });

  it("does not redirect when already on /login", async () => {
    useAuthStore.getState().setSession("u_7", { id: 7, username: "alice" });
    mock.onPost("/auth/login").reply(401, { detail: "invalid_credentials" });
    const replaceMock = vi.fn();
    vi.stubGlobal("location", { ...window.location, pathname: "/login", replace: replaceMock });

    await expect(api.post("/auth/login", {})).rejects.toThrow();
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
```

Create `frontend/lib/api.ts`:

```typescript
"use client";

import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

import { useAuthStore } from "./auth-store";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080",
  timeout: 30_000,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().clearSession();
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
        window.location.replace("/login");
      }
    }
    return Promise.reject(error);
  },
);
```

- [ ] **Step 6: Run frontend tests + typecheck**

```bash
cd frontend
$NPM test && $NPM run typecheck
```

Expected: all tests pass; typecheck exit 0.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/vitest.setup.ts frontend/lib
git commit -m "feat: add frontend test setup, auth store, and axios instance"
```

---

### Task 8: AuthGuard, Login Page, and Protected Layout

**Files:**
- Create: `frontend/components/AuthGuard.tsx`, `frontend/components/AuthGuard.test.tsx`
- Create: `frontend/app/login/page.tsx`, `frontend/app/login/page.test.tsx`
- Create: `frontend/app/(protected)/layout.tsx`
- Move: `frontend/app/page.tsx` → `frontend/app/(protected)/page.tsx` (with logout button added)

- [ ] **Step 1: AuthGuard tests + impl**

Create `frontend/components/AuthGuard.test.tsx`:

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthGuard } from "./AuthGuard";
import { api } from "../lib/api";
import { useAuthStore } from "../lib/auth-store";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: replaceMock }),
}));

describe("AuthGuard", () => {
  let mock: MockAdapter;

  beforeEach(() => {
    mock = new MockAdapter(api);
    useAuthStore.getState().clearSession();
    localStorage.clear();
    replaceMock.mockClear();
  });

  afterEach(() => mock.restore());

  it("redirects to /login when no token", async () => {
    render(<AuthGuard><div>protected</div></AuthGuard>);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("protected")).toBeNull();
  });

  it("renders children after /auth/me succeeds", async () => {
    useAuthStore.getState().setSession("u_7", { id: 7, username: "alice" });
    mock.onGet("/auth/me").reply(200, { id: 7, username: "alice", created_at: "2026-04-25T10:00:00Z" });
    render(<AuthGuard><div>protected</div></AuthGuard>);
    expect(await screen.findByText("protected")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("clears session and redirects when /auth/me returns 401", async () => {
    useAuthStore.getState().setSession("u_7", { id: 7, username: "alice" });
    mock.onGet("/auth/me").reply(401, { detail: "invalid_token" });
    render(<AuthGuard><div>protected</div></AuthGuard>);
    await waitFor(() => expect(useAuthStore.getState().token).toBeNull());
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });
});
```

Create `frontend/components/AuthGuard.tsx`:

```typescript
"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { api } from "../lib/api";
import { useAuthStore } from "../lib/auth-store";

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const setSession = useAuthStore((s) => s.setSession);
  const clearSession = useAuthStore((s) => s.clearSession);
  // Wait for Zustand persist to finish reading from localStorage before
  // deciding whether the user is authenticated. Without this gate, a page
  // reload with a valid persisted token briefly sees `token === null` and
  // redirects to /login before hydration completes.
  const [hydrated, setHydrated] = useState(() => useAuthStore.persist.hasHydrated());
  const [verified, setVerified] = useState(false);

  useEffect(() => {
    if (hydrated) return;
    const unsub = useAuthStore.persist.onFinishHydration(() => setHydrated(true));
    return unsub;
  }, [hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    api
      .get("/auth/me")
      .then((res) => {
        if (cancelled) return;
        setSession(token, { id: res.data.id, username: res.data.username });
        setVerified(true);
      })
      .catch(() => {
        if (cancelled) return;
        clearSession();
        router.replace("/login");
      });
    return () => {
      cancelled = true;
    };
  }, [hydrated, token, router, setSession, clearSession]);

  if (!hydrated || !verified) return null;
  return <>{children}</>;
}
```

- [ ] **Step 2: Login page tests + impl**

Create `frontend/app/login/page.test.tsx`:

```typescript
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "./page";
import { api } from "../../lib/api";
import { useAuthStore } from "../../lib/auth-store";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: pushMock }),
}));

describe("LoginPage", () => {
  let mock: MockAdapter;

  beforeEach(() => {
    mock = new MockAdapter(api);
    useAuthStore.getState().clearSession();
    localStorage.clear();
    pushMock.mockClear();
  });

  afterEach(() => mock.restore());

  it("submits credentials and stores session on success", async () => {
    mock.onPost("/auth/login").reply(200, {
      token: "u_7",
      user: { id: 7, username: "alice" },
    });
    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/username/i), "alice");
    await userEvent.type(screen.getByLabelText(/password/i), "hunter2");
    fireEvent.click(screen.getByRole("button", { name: /sign in|login/i }));

    await waitFor(() => expect(useAuthStore.getState().token).toBe("u_7"));
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("shows the invalid_credentials error on 401", async () => {
    mock.onPost("/auth/login").reply(401, { detail: "invalid_credentials" });
    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/username/i), "alice");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    fireEvent.click(screen.getByRole("button", { name: /sign in|login/i }));

    expect(await screen.findByTestId("login-error")).toHaveAttribute(
      "data-error-key",
      "auth.error.invalid_credentials",
    );
    expect(useAuthStore.getState().token).toBeNull();
  });
});
```

Create `frontend/app/login/page.tsx`:

```typescript
"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { isAxiosError } from "axios";

import { api } from "../../lib/api";
import { useAuthStore } from "../../lib/auth-store";

const ERROR_KEYS: Record<string, string> = {
  invalid_credentials: "auth.error.invalid_credentials",
};

// Hardcoded English fallbacks shown to users until the i18n layer lands.
// `data-error-key` carries the stable code for tests and future i18n lookup.
const ERROR_FALLBACKS: Record<string, string> = {
  "auth.error.invalid_credentials": "Incorrect username or password.",
  "auth.error.network": "Could not reach the server. Please try again.",
};

export default function LoginPage() {
  const router = useRouter();
  const setSession = useAuthStore((s) => s.setSession);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErrorKey(null);
    setSubmitting(true);
    try {
      const res = await api.post<{
        token: string;
        user: { id: number; username: string };
      }>("/auth/login", { username, password });
      setSession(res.data.token, res.data.user);
      router.push("/");
    } catch (err) {
      if (isAxiosError(err) && err.response?.data?.detail) {
        const detail = err.response.data.detail as string;
        setErrorKey(ERROR_KEYS[detail] ?? "auth.error.network");
      } else {
        setErrorKey("auth.error.network");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg border border-border bg-white p-6 shadow-sm"
        aria-label="Login form"
      >
        <h1 className="text-xl font-semibold">KnowledgeDeck</h1>
        <div className="space-y-2">
          <label htmlFor="username" className="block text-sm">Username</label>
          <input
            id="username"
            name="username"
            type="text"
            autoComplete="username"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="password" className="block text-sm">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm"
          />
        </div>
        {errorKey ? (
          <div data-testid="login-error" data-error-key={errorKey} className="text-sm text-red-600">
            {ERROR_FALLBACKS[errorKey] ?? errorKey}
          </div>
        ) : null}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-foreground px-3 py-2 text-sm text-white disabled:opacity-50"
        >
          {submitting ? "..." : "Sign in"}
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 3: Move chat shell into protected route group + add logout button**

```bash
mkdir -p frontend/app/\(protected\)
git mv frontend/app/page.tsx frontend/app/\(protected\)/page.tsx
```

Replace `frontend/app/(protected)/page.tsx` with:

```typescript
"use client";

import { FileText, LogOut, MessageSquare, Presentation, Search } from "lucide-react";
import { useRouter } from "next/navigation";

import { useAuthStore } from "../../lib/auth-store";

const navItems = [
  { label: "Chat", icon: MessageSquare },
  { label: "Knowledge", icon: Search },
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

Create `frontend/app/(protected)/layout.tsx`:

```typescript
import type { ReactNode } from "react";

import { AuthGuard } from "../../components/AuthGuard";

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}
```

- [ ] **Step 4: Run full frontend test + typecheck**

```bash
cd frontend
$NPM test && $NPM run typecheck
```

Expected: all tests pass; typecheck exit 0.

- [ ] **Step 5: Run full backend suite as a sanity check**

```bash
cd backend
python3 -m pytest -v
```

Expected: still 31 tests passing.

- [ ] **Step 6: Commit**

```bash
git add frontend/components frontend/app/login frontend/app/\(protected\)
git commit -m "feat: add login page, AuthGuard, protected layout, and logout"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Implemented in |
|---|---|
| Settings additions (database_url, INITIAL_USER_*) and JWT removal | Task 1 |
| `users` table schema, ORM, Alembic migration, test fixture | Task 1 |
| `authenticate(session, username, password)` | Task 2 |
| `get_current_user` parsing `u_<id>` token | Task 3 |
| `POST /auth/login` returning `{token, user}` and `GET /auth/me` | Task 4 |
| First-user lifespan seed (idempotent, both env vars required) | Task 5 |
| CLI `create-user` and Dockerfile entrypoint running `alembic upgrade head` | Task 6 |
| Frontend deps + vitest + Zustand auth store + axios interceptor | Task 7 |
| Login page + AuthGuard + protected layout + logout button (client-only) | Task 8 |
| Error code contract (`invalid_credentials`, `invalid_token`) | Tasks 3, 4, 8 |

Items deliberately not in any task because they are explicitly out of MVP scope: password hashing, JWT, refresh, token revocation, login_logs, IP/UA, rate limiting, account_disabled, admin role enforcement, `/auth/logout` backend endpoint.

**2. Placeholder scan:** no `TBD`, `TODO`, "implement later", "add appropriate error handling", or "similar to Task N" present in the plan body.

**3. Type consistency:**
- `User`, `AuthUser`, `LoginRequest`, `LoginResponse`, `MeResponse`, `UserSummary`, `UserState` are spelled identically across all references.
- Function names (`authenticate`, `seed_initial_user`, `get_current_user`, `setSession`, `clearSession`) are consistent.
- Error code strings (`invalid_credentials`, `invalid_token`) appear identically in backend and frontend assertions.
- Token format `u_<id>` (lowercase prefix, integer id) is consistent across `get_current_user`, `/auth/login` response, AuthGuard test fixtures, and axios test fixtures.
