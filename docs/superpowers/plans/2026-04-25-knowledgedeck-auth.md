# KnowledgeDeck Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement JWT-based authentication, login/logout audit, admin CLI tooling, and a frontend login flow per [docs/superpowers/specs/2026-04-25-knowledgedeck-auth-design.md](../specs/2026-04-25-knowledgedeck-auth-design.md).

**Architecture:** Stateless JWT (HS256, 8h TTL) over `Authorization: Bearer` header. Postgres stores `users` (CITEXT email, argon2id password hash, role enum, is_active flag) and `login_logs` (open row on login, `logout_at` updated on logout). Backend exposes `/auth/login`, `/auth/logout`, `/auth/me`. First admin auto-seeded from env on FastAPI startup. Frontend stores token in `localStorage` via Zustand; axios interceptor attaches Bearer header and routes to `/login` on 401; protected pages live under `app/(protected)/` and are guarded by a client-side `<AuthGuard>`.

**Tech Stack:** SQLAlchemy 2.0 async + psycopg 3, Alembic, argon2-cffi, PyJWT, Typer, FastAPI lifespan, testcontainers-python (PostgreSQL); Next.js 15 client components, Zustand persist, axios, vitest + @testing-library/react.

---

## Scope

This plan implements every Section of the auth design spec **In Scope** list. It does not implement Phase 4 admin web UI, refresh tokens, password reset emails, rate limiting, or the broader i18n architecture (only the error code contract is fixed here).

## File Structure

**Backend:**

- Modify `backend/pyproject.toml`: add `sqlalchemy>=2.0`, `psycopg[binary]>=3.2`, `alembic>=1.13`, `argon2-cffi>=23.1`, `pyjwt>=2.9`, `email-validator>=2.2`, `typer>=0.12`; dev: `testcontainers[postgresql]>=4.8`.
- Modify `backend/app/core/config.py`: add `database_url`, `initial_admin_email`, `initial_admin_password`; raise `jwt_access_token_minutes` default to 480.
- Modify `backend/tests/test_config.py`: assert new defaults.
- Create `backend/app/core/security.py`: argon2 hash/verify helpers; JWT encode/decode helpers; module-level `_DUMMY_HASH` constant.
- Create `backend/tests/test_security.py`: unit tests for hash + JWT round trips.
- Create `backend/app/db/__init__.py`, `backend/app/db/base.py`: SQLAlchemy declarative base + async engine + `async_session_factory` + `get_db` dependency.
- Create `backend/app/db/models.py`: `UserRole` enum, `User`, `LoginLog`.
- Create `backend/tests/test_models.py`: import-only smoke test (defers DB-touching assertions to fixtures from Task 3).
- Create `backend/app/db/migrations/env.py`, `backend/app/db/migrations/script.py.mako`, `backend/alembic.ini`, `backend/app/db/migrations/versions/0001_initial.py`: Alembic configuration and the first migration creating `citext` extension, `user_role` enum, and both tables.
- Create `backend/tests/conftest.py`: testcontainers Postgres fixture + per-test transaction rollback fixture.
- Create `backend/tests/test_migration.py`: smoke test that `alembic upgrade head` produces the expected schema.
- Create `backend/app/services/auth_service.py`: `authenticate`, `open_login_log`, `close_latest_login_log`.
- Create `backend/tests/test_auth_service.py`.
- Create `backend/app/api/deps.py`: `get_current_user`, `get_current_admin`.
- Create `backend/tests/test_deps.py`.
- Create `backend/app/api/auth.py`: `/auth/login`, `/auth/logout`, `/auth/me` router.
- Create `backend/tests/test_auth_login.py`, `backend/tests/test_auth_logout.py`, `backend/tests/test_auth_me.py`.
- Modify `backend/app/main.py`: register auth router; wire FastAPI `lifespan` that runs the admin seed.
- Create `backend/app/startup.py`: `seed_initial_admin` lifespan helper.
- Create `backend/tests/test_seed_admin.py`.
- Create `backend/app/cli.py`: Typer app with `create-user`, `list-users`, `set-active`, `reset-password`.
- Create `backend/tests/test_cli.py`.
- Modify `backend/Dockerfile`: install Alembic config; entrypoint runs `alembic upgrade head` before uvicorn.
- Modify `docker-compose.yml`: backend service mounts the migrations folder; explicit entrypoint override if needed.
- Modify `.env.example`: add `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`.

**Frontend:**

- Modify `frontend/package.json`: add `axios>=1.7`, `zustand>=5.0`; dev: `vitest`, `@vitejs/plugin-react`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`.
- Create `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`: vitest + jsdom + RTL setup.
- Create `frontend/lib/auth-store.ts`: Zustand store with `persist`/`localStorage`.
- Create `frontend/lib/auth-store.test.ts`.
- Create `frontend/lib/api.ts`: shared axios instance + Bearer + 401 interceptor.
- Create `frontend/lib/api.test.ts`.
- Create `frontend/components/AuthGuard.tsx`: client-side route guard.
- Create `frontend/components/AuthGuard.test.tsx`.
- Create `frontend/app/login/page.tsx`: login form (email + password).
- Create `frontend/app/login/page.test.tsx`.
- Create `frontend/app/(protected)/layout.tsx`: wraps protected pages in `<AuthGuard>`.
- Move `frontend/app/page.tsx` → `frontend/app/(protected)/page.tsx`: existing chat shell becomes protected; add a logout button.

---

## Conventions Used Below

- Backend tests run with system `python3` (3.10) per the existing pattern.
- Frontend tooling uses the verified node24 path: `NODE_DIR=/homepool2/tobyleung/actions-runner/externals.2.330.0/node24/bin` and the npm cli at `$NODE_DIR/../lib/node_modules/npm/bin/npm-cli.js`. Each frontend command in this plan writes the helper as `NPM` for brevity.
- All commits go on the current `dev` branch unless explicitly otherwise. Per `AGENTS.md`, this multi-task feature work could optionally be done on a `feat/auth` branch off `dev` and merged back via PR; the plan uses `dev` directly to match the existing scaffold pattern but the executor may choose to branch.
- Every task ends in a commit. Test commands are written so a clean run produces a non-zero exit only on failure.

---

### Task 1: Backend Dependencies and Settings

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/test_config.py`

- [ ] **Step 1: Update the failing settings test first**

Edit `backend/tests/test_config.py` to assert the new defaults. Replace the contents with:

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
    assert settings.jwt_access_token_minutes == 480
    assert settings.database_url == (
        "postgresql+psycopg://knowledgedeck:change-me@knowledgedeck_postgres:5432/knowledgedeck"
    )
    assert settings.initial_admin_email == ""
    assert settings.initial_admin_password == ""


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


def test_settings_accept_auth_overrides() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        initial_admin_email="admin@example.test",
        initial_admin_password="secret123",
        jwt_access_token_minutes=60,
    )

    assert settings.database_url == "postgresql+psycopg://test:test@localhost:5432/test"
    assert settings.initial_admin_email == "admin@example.test"
    assert settings.initial_admin_password == "secret123"
    assert settings.jwt_access_token_minutes == 60
```

- [ ] **Step 2: Run the test to confirm it fails on the new assertions**

```bash
cd backend
python3 -m pytest tests/test_config.py -v
```

Expected: `test_settings_defaults_match_local_development` fails on the `jwt_access_token_minutes == 480` assertion (currently 60), `database_url` (missing), and `initial_admin_email` (missing).

- [ ] **Step 3: Update `backend/app/core/config.py`**

Replace the `Settings` class so it reads:

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "KnowledgeDeck"
    environment: str = "local"
    api_prefix: str = "/api"

    database_url: str = (
        "postgresql+psycopg://knowledgedeck:change-me@knowledgedeck_postgres:5432/knowledgedeck"
    )

    jwt_secret_key: str = Field(default="change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 480

    initial_admin_email: str = ""
    initial_admin_password: str = ""

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

- [ ] **Step 4: Update `backend/pyproject.toml`**

Replace the `[project]` and `[project.optional-dependencies]` blocks with:

```toml
[project]
name = "knowledgedeck-backend"
version = "0.1.0"
description = "FastAPI backend for KnowledgeDeck AI Platform"
requires-python = ">=3.11"
dependencies = [
    "alembic>=1.13.0",
    "argon2-cffi>=23.1.0",
    "email-validator>=2.2.0",
    "fastapi>=0.115.0",
    "httpx>=0.27.0",
    "psycopg[binary]>=3.2.0",
    "pydantic-settings>=2.4.0",
    "pyjwt>=2.9.0",
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

Note: switching to `asyncio_mode = "auto"` makes all `async def` test and fixture functions run on the event loop without an explicit `@pytest.mark.asyncio` marker. Existing markers in the test files remain valid (they are no-ops in auto mode).

- [ ] **Step 5: Update `.env.example`**

Insert these lines after the `JWT_ACCESS_TOKEN_MINUTES=60` line and change that value to `480`:

```env
JWT_ACCESS_TOKEN_MINUTES=480

INITIAL_ADMIN_EMAIL=admin@knowledgedeck.local
INITIAL_ADMIN_PASSWORD=change-me-on-first-deploy
```

(The order is: keep the existing `JWT_SECRET_KEY` and `JWT_ALGORITHM`, change `JWT_ACCESS_TOKEN_MINUTES` from `60` to `480`, append the two `INITIAL_ADMIN_*` lines below them.)

- [ ] **Step 6: Install the new backend dependencies locally**

```bash
cd backend
python3 -m pip install --user --upgrade 'sqlalchemy>=2.0.32' 'psycopg[binary]>=3.2.0' 'alembic>=1.13.0' 'argon2-cffi>=23.1.0' 'pyjwt>=2.9.0' 'email-validator>=2.2.0' 'typer>=0.12.0' 'testcontainers[postgresql]>=4.8.0'
```

Expected: pip prints `Successfully installed ...` for each package and any of their transitive deps.

- [ ] **Step 7: Re-run the settings tests**

```bash
cd backend
python3 -m pytest tests/test_config.py -v
```

Expected: all three tests pass.

- [ ] **Step 8: Run the full backend test suite to confirm no regressions**

```bash
cd backend
python3 -m pytest -v
```

Expected: all 7 tests pass (existing 6 + the new auth override test).

- [ ] **Step 9: Commit**

```bash
git add backend/pyproject.toml backend/app/core/config.py backend/tests/test_config.py .env.example
git commit -m "feat: add auth-related backend settings and dependencies"
```

---

### Task 2: SQLAlchemy Base, Engine, and ORM Models

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/models.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing import test**

Create `backend/tests/test_models.py`:

```python
from app.db.models import LoginLog, User, UserRole


def test_user_role_enum_values() -> None:
    assert UserRole.USER.value == "user"
    assert UserRole.ADMIN.value == "admin"


def test_user_table_metadata() -> None:
    assert User.__tablename__ == "users"
    columns = {c.name for c in User.__table__.columns}
    assert columns == {
        "id",
        "email",
        "password_hash",
        "role",
        "is_active",
        "created_at",
        "updated_at",
    }


def test_login_log_table_metadata() -> None:
    assert LoginLog.__tablename__ == "login_logs"
    columns = {c.name for c in LoginLog.__table__.columns}
    assert columns == {
        "id",
        "user_id",
        "login_at",
        "logout_at",
        "ip_address",
        "user_agent",
        "created_at",
    }
```

- [ ] **Step 2: Run the test to confirm it fails on import**

```bash
cd backend
python3 -m pytest tests/test_models.py -v
```

Expected: collection error `ModuleNotFoundError: No module named 'app.db'`.

- [ ] **Step 3: Create the SQLAlchemy declarative base and engine**

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
    async with async_session_factory()() as session:
        yield session
```

- [ ] **Step 4: Create the ORM models**

Create `backend/app/db/models.py`:

```python
import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=UserRole.USER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    login_logs: Mapped[list["LoginLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class LoginLog(Base):
    __tablename__ = "login_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    logout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str] = mapped_column(INET, nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="login_logs")

    __table_args__ = (
        Index("idx_login_logs_user_login", "user_id", login_at.desc()),
        Index(
            "idx_login_logs_open_session",
            "user_id",
            postgresql_where=logout_at.is_(None),
        ),
    )
```

- [ ] **Step 5: Run the test to confirm it passes**

```bash
cd backend
python3 -m pytest tests/test_models.py -v
```

Expected: all three tests pass.

- [ ] **Step 6: Run the full backend test suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: all tests pass (10 total).

- [ ] **Step 7: Commit**

```bash
git add backend/app/db backend/tests/test_models.py
git commit -m "feat: add SQLAlchemy base, engine, and auth ORM models"
```

---

### Task 3: Alembic Initial Migration and Test Database Fixture

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/app/db/migrations/__init__.py`
- Create: `backend/app/db/migrations/env.py`
- Create: `backend/app/db/migrations/script.py.mako`
- Create: `backend/app/db/migrations/versions/__init__.py`
- Create: `backend/app/db/migrations/versions/0001_initial.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_migration.py`

- [ ] **Step 1: Write the failing migration smoke test**

Create `backend/tests/test_migration.py`:

```python
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_migration_creates_users_and_login_logs_tables(db_session) -> None:
    result = await db_session.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('users', 'login_logs')
            ORDER BY table_name
            """
        )
    )
    tables = [row[0] for row in result.all()]
    assert tables == ["login_logs", "users"]


@pytest.mark.asyncio
async def test_migration_creates_user_role_enum(db_session) -> None:
    result = await db_session.execute(
        text("SELECT unnest(enum_range(NULL::user_role))::text ORDER BY 1")
    )
    values = [row[0] for row in result.all()]
    assert values == ["admin", "user"]


@pytest.mark.asyncio
async def test_migration_creates_citext_extension(db_session) -> None:
    result = await db_session.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'citext'")
    )
    assert result.scalar_one_or_none() == 1
```

- [ ] **Step 2: Add the conftest with a testcontainers Postgres fixture**

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
        # testcontainers returns a SQLAlchemy URL using psycopg2; rewrite it for psycopg 3.
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
    # NullPool ensures every test gets its own physical connection,
    # so concurrent sessions opened from CLI commands don't deadlock.
    engine = create_async_engine(postgres_url, future=True, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
def _patch_app_db(monkeypatch, shared_engine: AsyncEngine, postgres_url: str) -> None:
    """Make app.db.base.get_engine() / async_session_factory() share the test engine.

    Without this, code under test (auth API handlers, CLI commands, the seed lifespan)
    would create a brand-new engine pointed at the production DSN.
    """
    from app.core.config import get_settings
    from app.db import base as db_base

    monkeypatch.setenv("DATABASE_URL", postgres_url)
    get_settings.cache_clear()
    factory = async_sessionmaker(shared_engine, expire_on_commit=False)
    monkeypatch.setattr(db_base, "_engine", shared_engine, raising=False)
    monkeypatch.setattr(db_base, "_session_factory", factory, raising=False)


@pytest_asyncio.fixture()
async def db_session(shared_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Per-test clean DB state via TRUNCATE; tests may freely commit.

    TRUNCATE on `users` cascades to `login_logs` (FK ON DELETE CASCADE).
    Sequences are reset so id assertions stay stable across tests.
    """
    factory = async_sessionmaker(shared_engine, expire_on_commit=False)
    async with factory() as setup:
        await setup.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await setup.commit()

    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
```

Notes:

- `testcontainers[postgresql]` requires a running Docker daemon on the host. If unavailable, the auth design spec's open item permits switching to `pytest-postgresql`; replace the `postgres_url` fixture accordingly and update `pyproject.toml` deps.
- TRUNCATE rather than transaction rollback is used because several tests exercise code paths (CLI, login endpoint, seed) that open their own sessions and commit; a rollback fixture cannot bridge those independent sessions.

- [ ] **Step 3: Add the Alembic configuration files**

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

Create `backend/app/db/migrations/__init__.py`:

```python
```

Create `backend/app/db/migrations/versions/__init__.py`:

```python
```

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

Note: the env file uses synchronous engine config because Alembic's `command.upgrade` and `alembic upgrade head` are synchronous. The `database_url` in production starts with `postgresql+psycopg://` which is also a valid sync DSN for psycopg 3.

- [ ] **Step 4: Write the initial migration**

Create `backend/app/db/migrations/versions/0001_initial.py`:

```python
"""initial users and login_logs

Revision ID: 0001
Revises:
Create Date: 2026-04-25 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE TYPE user_role AS ENUM ('user', 'admin')")

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("user", "admin", name="user_role", create_type=False),
            nullable=False,
            server_default="user",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
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
    )
    op.create_index("idx_users_email", "users", ["email"])

    op.create_table(
        "login_logs",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "login_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("logout_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", postgresql.INET, nullable=False),
        sa.Column("user_agent", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_login_logs_user_login",
        "login_logs",
        ["user_id", sa.text("login_at DESC")],
    )
    op.create_index(
        "idx_login_logs_open_session",
        "login_logs",
        ["user_id"],
        postgresql_where=sa.text("logout_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_login_logs_open_session", table_name="login_logs")
    op.drop_index("idx_login_logs_user_login", table_name="login_logs")
    op.drop_table("login_logs")
    op.drop_index("idx_users_email", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE user_role")
```

- [ ] **Step 5: Run the migration smoke tests**

```bash
cd backend
python3 -m pytest tests/test_migration.py -v
```

Expected: all three tests pass. Testcontainers downloads `postgres:16-alpine` on first run; subsequent runs reuse the cached image.

- [ ] **Step 6: Run the full backend test suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: all tests pass (13 total).

- [ ] **Step 7: Commit**

```bash
git add backend/alembic.ini backend/app/db/migrations backend/tests/conftest.py backend/tests/test_migration.py
git commit -m "feat: add alembic config, initial migration, and test db fixture"
```

---

### Task 4: Security Utilities (argon2 + JWT)

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: Write the failing security tests**

Create `backend/tests/test_security.py`:

```python
import time

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    DUMMY_HASH,
)


def test_hash_and_verify_round_trip() -> None:
    digest = hash_password("correct horse battery staple")
    assert digest != "correct horse battery staple"
    assert verify_password(digest, "correct horse battery staple") is True
    assert verify_password(digest, "wrong password") is False


def test_dummy_hash_is_a_valid_argon2_hash() -> None:
    assert DUMMY_HASH.startswith("$argon2")
    assert verify_password(DUMMY_HASH, "anything") is False


def test_create_and_decode_access_token_round_trip() -> None:
    settings = Settings(jwt_secret_key="test-secret-key-12345")
    token = create_access_token(
        subject="42",
        email="user@example.com",
        role="user",
        settings=settings,
    )
    payload = decode_access_token(token, settings=settings)
    assert payload["sub"] == "42"
    assert payload["email"] == "user@example.com"
    assert payload["role"] == "user"
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_decode_access_token_rejects_expired_token() -> None:
    settings = Settings(
        jwt_secret_key="test-secret-key-12345",
        jwt_access_token_minutes=0,
    )
    token = create_access_token(subject="1", email="a@b.c", role="user", settings=settings)
    time.sleep(1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, settings=settings)


def test_decode_access_token_rejects_tampered_signature() -> None:
    settings = Settings(jwt_secret_key="test-secret-key-12345")
    token = create_access_token(subject="1", email="a@b.c", role="user", settings=settings)
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered, settings=settings)


def test_decode_access_token_rejects_wrong_secret() -> None:
    settings_a = Settings(jwt_secret_key="secret-aaaaaaaa")
    settings_b = Settings(jwt_secret_key="secret-bbbbbbbb")
    token = create_access_token(subject="1", email="a@b.c", role="user", settings=settings_a)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, settings=settings_b)
```

- [ ] **Step 2: Run the test to confirm it fails on import**

```bash
cd backend
python3 -m pytest tests/test_security.py -v
```

Expected: collection error `ModuleNotFoundError: No module named 'app.core.security'`.

- [ ] **Step 3: Implement the security module**

Create `backend/app/core/security.py`:

```python
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings, get_settings

_hasher = PasswordHasher()

# Pre-computed argon2 hash used for timing-attack mitigation when the supplied
# email does not exist. Verifying any password against this hash takes the same
# time as a real password check.
DUMMY_HASH = _hasher.hash("__knowledgedeck_dummy_password__")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_access_token(
    *,
    subject: str,
    email: str,
    role: str,
    settings: Settings | None = None,
) -> str:
    cfg = settings or get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=cfg.jwt_access_token_minutes)).timestamp()),
    }
    return jwt.encode(payload, cfg.jwt_secret_key, algorithm=cfg.jwt_algorithm)


def decode_access_token(
    token: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    return jwt.decode(token, cfg.jwt_secret_key, algorithms=[cfg.jwt_algorithm])
```

- [ ] **Step 4: Run the security tests**

```bash
cd backend
python3 -m pytest tests/test_security.py -v
```

Expected: all six tests pass.

- [ ] **Step 5: Run the full backend test suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: all tests pass (19 total).

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat: add argon2 password hashing and JWT helpers"
```

---

### Task 5: Auth Service

**Files:**
- Create: `backend/app/services/auth_service.py`
- Create: `backend/tests/test_auth_service.py`

- [ ] **Step 1: Write the failing service tests**

Create `backend/tests/test_auth_service.py`:

```python
from datetime import datetime

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import LoginLog, User, UserRole
from app.services.auth_service import (
    authenticate,
    close_latest_login_log,
    open_login_log,
)


@pytest.fixture()
async def seeded_user(db_session) -> User:
    user = User(
        email="alice@example.test",
        password_hash=hash_password("hunter2hunter2"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_authenticate_success(db_session, seeded_user: User) -> None:
    user = await authenticate(db_session, "alice@example.test", "hunter2hunter2")
    assert user is not None
    assert user.id == seeded_user.id


@pytest.mark.asyncio
async def test_authenticate_is_case_insensitive(db_session, seeded_user: User) -> None:
    user = await authenticate(db_session, "Alice@Example.TEST", "hunter2hunter2")
    assert user is not None
    assert user.id == seeded_user.id


@pytest.mark.asyncio
async def test_authenticate_wrong_password(db_session, seeded_user: User) -> None:
    user = await authenticate(db_session, "alice@example.test", "wrong")
    assert user is None


@pytest.mark.asyncio
async def test_authenticate_unknown_email_runs_dummy_verify(db_session) -> None:
    user = await authenticate(db_session, "nobody@example.test", "anything")
    assert user is None


@pytest.mark.asyncio
async def test_open_login_log_inserts_row(db_session, seeded_user: User) -> None:
    await open_login_log(
        db_session,
        user_id=seeded_user.id,
        ip_address="10.0.0.1",
        user_agent="pytest",
    )
    await db_session.commit()
    row = await db_session.scalar(
        select(LoginLog).where(LoginLog.user_id == seeded_user.id)
    )
    assert row is not None
    assert row.logout_at is None
    assert row.ip_address == "10.0.0.1"
    assert row.user_agent == "pytest"


@pytest.mark.asyncio
async def test_close_latest_login_log_updates_only_most_recent_open_row(
    db_session, seeded_user: User
) -> None:
    await open_login_log(db_session, user_id=seeded_user.id, ip_address="10.0.0.1", user_agent="ua-1")
    await db_session.commit()
    await open_login_log(db_session, user_id=seeded_user.id, ip_address="10.0.0.2", user_agent="ua-2")
    await db_session.commit()

    closed = await close_latest_login_log(db_session, user_id=seeded_user.id)
    await db_session.commit()
    assert closed is True

    rows = (
        await db_session.scalars(
            select(LoginLog).where(LoginLog.user_id == seeded_user.id).order_by(LoginLog.login_at)
        )
    ).all()
    assert len(rows) == 2
    assert rows[0].logout_at is None  # older row stays open
    assert isinstance(rows[1].logout_at, datetime)


@pytest.mark.asyncio
async def test_close_latest_login_log_returns_false_when_no_open_row(
    db_session, seeded_user: User
) -> None:
    closed = await close_latest_login_log(db_session, user_id=seeded_user.id)
    assert closed is False
```

Note: with `asyncio_mode = "auto"` set in `pyproject.toml` (Task 1), `@pytest.fixture()` decorating an `async def` function works directly — no `@pytest_asyncio.fixture` needed and the `@pytest.mark.asyncio` markers are redundant (kept for explicitness).

- [ ] **Step 2: Run the test to confirm it fails on import**

```bash
cd backend
python3 -m pytest tests/test_auth_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.auth_service'`.

- [ ] **Step 3: Implement the auth service**

Create `backend/app/services/auth_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import DUMMY_HASH, verify_password
from app.db.models import LoginLog, User


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        # Run a verify call against DUMMY_HASH so timing matches the real path.
        verify_password(DUMMY_HASH, password)
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


async def open_login_log(
    session: AsyncSession,
    *,
    user_id: int,
    ip_address: str,
    user_agent: str,
) -> LoginLog:
    log = LoginLog(user_id=user_id, ip_address=ip_address, user_agent=user_agent)
    session.add(log)
    await session.flush()
    return log


async def close_latest_login_log(session: AsyncSession, *, user_id: int) -> bool:
    stmt = (
        select(LoginLog)
        .where(LoginLog.user_id == user_id, LoginLog.logout_at.is_(None))
        .order_by(LoginLog.login_at.desc())
        .limit(1)
    )
    log = await session.scalar(stmt)
    if log is None:
        return False
    from sqlalchemy import func

    log.logout_at = func.now()
    await session.flush()
    return True
```

Also update `backend/app/services/__init__.py` so it exports the new symbols (keeps existing re-exports):

```python
from app.services.auth_service import authenticate, close_latest_login_log, open_login_log
from app.services.model_clients import ChatModelClient, EmbeddingClient

__all__ = [
    "ChatModelClient",
    "EmbeddingClient",
    "authenticate",
    "close_latest_login_log",
    "open_login_log",
]
```

- [ ] **Step 4: Run the auth service tests**

```bash
cd backend
python3 -m pytest tests/test_auth_service.py -v
```

Expected: all seven tests pass.

- [ ] **Step 5: Run the full backend test suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: all tests pass (26 total).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/auth_service.py backend/app/services/__init__.py backend/tests/test_auth_service.py
git commit -m "feat: add auth service with timing-safe authenticate"
```

---

### Task 6: Auth Dependencies

**Files:**
- Create: `backend/app/api/deps.py`
- Create: `backend/tests/test_deps.py`

- [ ] **Step 1: Write the failing dependency tests**

Create `backend/tests/test_deps.py`:

```python
import pytest
from fastapi import HTTPException

from app.api.deps import get_current_admin, get_current_user
from app.core.security import create_access_token, hash_password
from app.db.models import User, UserRole


@pytest.fixture()
async def active_user(db_session) -> User:
    user = User(
        email="alice@example.test",
        password_hash=hash_password("hunter2hunter2"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture()
async def admin_user(db_session) -> User:
    user = User(
        email="boss@example.test",
        password_hash=hash_password("admin-pwd-1234"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_current_user_resolves_active_user(db_session, active_user: User) -> None:
    token = create_access_token(subject=str(active_user.id), email=active_user.email, role="user")
    user = await get_current_user(authorization=f"Bearer {token}", session=db_session)
    assert user.id == active_user.id


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
    assert exc.value.detail == "invalid_token"


@pytest.mark.asyncio
async def test_get_current_user_rejects_malformed_token(db_session) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization="Bearer not-a-jwt", session=db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_expired_token(db_session, active_user: User) -> None:
    from app.core.config import Settings

    expired_settings = Settings(jwt_access_token_minutes=0)
    token = create_access_token(
        subject=str(active_user.id), email=active_user.email, role="user", settings=expired_settings
    )
    import time as _t

    _t.sleep(1)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization=f"Bearer {token}", session=db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_disabled_user(db_session, active_user: User) -> None:
    active_user.is_active = False
    await db_session.commit()
    token = create_access_token(subject=str(active_user.id), email=active_user.email, role="user")
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization=f"Bearer {token}", session=db_session)
    assert exc.value.status_code == 403
    assert exc.value.detail == "account_disabled"


@pytest.mark.asyncio
async def test_get_current_admin_allows_admin(db_session, admin_user: User) -> None:
    token = create_access_token(subject=str(admin_user.id), email=admin_user.email, role="admin")
    user = await get_current_user(authorization=f"Bearer {token}", session=db_session)
    admin = await get_current_admin(user=user)
    assert admin.id == admin_user.id


@pytest.mark.asyncio
async def test_get_current_admin_rejects_user_role(db_session, active_user: User) -> None:
    token = create_access_token(subject=str(active_user.id), email=active_user.email, role="user")
    user = await get_current_user(authorization=f"Bearer {token}", session=db_session)
    with pytest.raises(HTTPException) as exc:
        await get_current_admin(user=user)
    assert exc.value.status_code == 403
    assert exc.value.detail == "admin_required"
```

- [ ] **Step 2: Run the test to confirm it fails on import**

```bash
cd backend
python3 -m pytest tests/test_deps.py -v
```

Expected: collection error `ModuleNotFoundError: No module named 'app.api.deps'`.

- [ ] **Step 3: Implement the dependencies**

Create `backend/app/api/deps.py`:

```python
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.base import get_db
from app.db.models import User, UserRole


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:  # covers Expired, InvalidSignature, DecodeError, etc.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc

    sub = payload.get("sub")
    if not sub or not sub.isdigit():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    user = await session.get(User, int(sub))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="user_not_found")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="account_disabled")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="admin_required")
    return user
```

- [ ] **Step 4: Run the dependency tests**

```bash
cd backend
python3 -m pytest tests/test_deps.py -v
```

Expected: all eight tests pass.

- [ ] **Step 5: Run the full backend test suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: all tests pass (34 total).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/deps.py backend/tests/test_deps.py
git commit -m "feat: add get_current_user and get_current_admin deps"
```

---

### Task 7: Auth API Endpoints

**Files:**
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_auth_login.py`
- Create: `backend/tests/test_auth_logout.py`
- Create: `backend/tests/test_auth_me.py`

- [ ] **Step 1: Write the failing endpoint tests**

Create `backend/tests/test_auth_login.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import LoginLog, User, UserRole


@pytest.fixture()
async def seeded_user(db_session) -> User:
    user = User(
        email="alice@example.test",
        password_hash=hash_password("hunter2hunter2"),
        role=UserRole.USER,
        is_active=True,
    )
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
async def test_login_success_returns_token_and_writes_log(
    http_client, db_session, seeded_user: User
) -> None:
    response = await http_client.post(
        "/auth/login",
        json={"email": "alice@example.test", "password": "hunter2hunter2"},
        headers={"User-Agent": "pytest-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 480 * 60
    assert body["user"]["email"] == "alice@example.test"
    assert body["user"]["role"] == "user"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20

    log = await db_session.scalar(select(LoginLog).where(LoginLog.user_id == seeded_user.id))
    assert log is not None
    assert log.user_agent == "pytest-1"
    assert log.logout_at is None


@pytest.mark.asyncio
async def test_login_email_is_case_insensitive(http_client, seeded_user: User) -> None:
    response = await http_client.post(
        "/auth/login",
        json={"email": "Alice@Example.TEST", "password": "hunter2hunter2"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_login_wrong_password_returns_invalid_credentials(
    http_client, seeded_user: User
) -> None:
    response = await http_client.post(
        "/auth/login",
        json={"email": "alice@example.test", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_credentials"}


@pytest.mark.asyncio
async def test_login_unknown_email_returns_invalid_credentials(http_client) -> None:
    response = await http_client.post(
        "/auth/login",
        json={"email": "nobody@example.test", "password": "anything"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_credentials"}


@pytest.mark.asyncio
async def test_login_disabled_user_returns_account_disabled(
    http_client, db_session, seeded_user: User
) -> None:
    seeded_user.is_active = False
    await db_session.commit()
    response = await http_client.post(
        "/auth/login",
        json={"email": "alice@example.test", "password": "hunter2hunter2"},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "account_disabled"}


@pytest.mark.asyncio
async def test_login_validation_error_returns_422(http_client) -> None:
    response = await http_client.post("/auth/login", json={"email": "not-an-email"})
    assert response.status_code == 422
```

Create `backend/tests/test_auth_logout.py`:

```python
import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.models import LoginLog, User, UserRole
from app.services.auth_service import open_login_log


@pytest.fixture()
async def seeded_user(db_session) -> User:
    user = User(
        email="bob@example.test",
        password_hash=hash_password("password1234"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture()
async def http_client():
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_logout_closes_latest_open_log(http_client, db_session, seeded_user: User) -> None:
    await open_login_log(db_session, user_id=seeded_user.id, ip_address="10.0.0.1", user_agent="ua")
    await db_session.commit()

    token = create_access_token(subject=str(seeded_user.id), email=seeded_user.email, role="user")
    response = await http_client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 204
    assert response.content == b""

    log = await db_session.scalar(select(LoginLog).where(LoginLog.user_id == seeded_user.id))
    assert log is not None
    assert log.logout_at is not None


@pytest.mark.asyncio
async def test_logout_with_no_open_log_still_returns_204(
    http_client, db_session, seeded_user: User
) -> None:
    token = create_access_token(subject=str(seeded_user.id), email=seeded_user.email, role="user")
    response = await http_client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_logout_with_expired_token_returns_401(http_client, seeded_user: User) -> None:
    from app.core.config import Settings

    expired = Settings(jwt_access_token_minutes=0)
    token = create_access_token(
        subject=str(seeded_user.id), email=seeded_user.email, role="user", settings=expired
    )
    import time

    time.sleep(1)
    response = await http_client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}
```

Create `backend/tests/test_auth_me.py`:

```python
import pytest

from app.core.security import create_access_token, hash_password
from app.db.models import User, UserRole


@pytest.fixture()
async def seeded_user(db_session) -> User:
    user = User(
        email="carol@example.test",
        password_hash=hash_password("password1234"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture()
async def http_client():
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_me_returns_current_user(http_client, seeded_user: User) -> None:
    token = create_access_token(subject=str(seeded_user.id), email=seeded_user.email, role="user")
    response = await http_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == seeded_user.id
    assert body["email"] == seeded_user.email
    assert body["role"] == "user"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_me_without_auth_header_returns_401(http_client) -> None:
    response = await http_client.get("/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


@pytest.mark.asyncio
async def test_me_with_unknown_subject_returns_user_not_found(http_client) -> None:
    token = create_access_token(subject="999999", email="ghost@example.test", role="user")
    response = await http_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json() == {"detail": "user_not_found"}


@pytest.mark.asyncio
async def test_me_disabled_user_returns_account_disabled(
    http_client, db_session, seeded_user: User
) -> None:
    seeded_user.is_active = False
    await db_session.commit()
    token = create_access_token(subject=str(seeded_user.id), email=seeded_user.email, role="user")
    response = await http_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json() == {"detail": "account_disabled"}
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
cd backend
python3 -m pytest tests/test_auth_login.py tests/test_auth_logout.py tests/test_auth_me.py -v
```

Expected: collection error or 404 — `app.api.auth` not yet imported, so `/auth/*` routes do not exist.

- [ ] **Step 3: Implement the auth router**

Create `backend/app/api/auth.py`:

```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.base import get_db
from app.db.models import User
from app.services.auth_service import (
    authenticate,
    close_latest_login_log,
    open_login_log,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserSummary(BaseModel):
    id: int
    email: str
    role: Literal["user", "admin"]


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    user: UserSummary


class MeResponse(BaseModel):
    id: int
    email: str
    role: Literal["user", "admin"]
    is_active: bool
    created_at: str


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> LoginResponse:
    user = await authenticate(session, body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="account_disabled")

    client_ip = request.client.host if request.client else "0.0.0.0"
    user_agent = request.headers.get("user-agent", "")
    await open_login_log(session, user_id=user.id, ip_address=client_ip, user_agent=user_agent)
    await session.commit()

    cfg = get_settings()
    token = create_access_token(subject=str(user.id), email=user.email, role=user.role.value)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=cfg.jwt_access_token_minutes * 60,
        user=UserSummary(id=user.id, email=user.email, role=user.role.value),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await close_latest_login_log(session, user_id=user.id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
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

(The lifespan that runs admin seed is added in Task 8 — keep `create_app` minimal here.)

- [ ] **Step 5: Run the auth endpoint tests**

```bash
cd backend
python3 -m pytest tests/test_auth_login.py tests/test_auth_logout.py tests/test_auth_me.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Run the full backend test suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: all tests pass (47 total).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/auth.py backend/app/main.py backend/tests/test_auth_login.py backend/tests/test_auth_logout.py backend/tests/test_auth_me.py
git commit -m "feat: add /auth/login, /auth/logout, /auth/me endpoints"
```

---

### Task 8: First Admin Seed Lifespan Hook

**Files:**
- Create: `backend/app/startup.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_seed_admin.py`

- [ ] **Step 1: Write the failing seed tests**

Create `backend/tests/test_seed_admin.py`:

```python
import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.security import hash_password
from app.db.models import User, UserRole
from app.startup import seed_initial_admin


@pytest.mark.asyncio
async def test_seed_creates_admin_when_email_does_not_exist(db_session) -> None:
    settings = Settings(
        initial_admin_email="seed-admin@example.test",
        initial_admin_password="seed-password",
    )
    await seed_initial_admin(db_session, settings=settings)
    await db_session.commit()

    user = await db_session.scalar(
        select(User).where(User.email == "seed-admin@example.test")
    )
    assert user is not None
    assert user.role == UserRole.ADMIN
    assert user.is_active is True


@pytest.mark.asyncio
async def test_seed_skips_when_email_already_exists(db_session) -> None:
    db_session.add(
        User(
            email="seed-admin@example.test",
            password_hash=hash_password("original-pwd-1234"),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    await db_session.commit()

    settings = Settings(
        initial_admin_email="seed-admin@example.test",
        initial_admin_password="different-pwd",
    )
    await seed_initial_admin(db_session, settings=settings)
    await db_session.commit()

    rows = (
        await db_session.scalars(select(User).where(User.email == "seed-admin@example.test"))
    ).all()
    assert len(rows) == 1
    # Password must remain the original (idempotent)
    from app.core.security import verify_password

    assert verify_password(rows[0].password_hash, "original-pwd-1234") is True
    assert verify_password(rows[0].password_hash, "different-pwd") is False


@pytest.mark.asyncio
async def test_seed_no_op_when_email_unset(db_session) -> None:
    settings = Settings(initial_admin_email="", initial_admin_password="anything")
    await seed_initial_admin(db_session, settings=settings)
    await db_session.commit()
    rows = (await db_session.scalars(select(User))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_seed_no_op_when_password_unset(db_session) -> None:
    settings = Settings(initial_admin_email="x@example.test", initial_admin_password="")
    await seed_initial_admin(db_session, settings=settings)
    await db_session.commit()
    rows = (await db_session.scalars(select(User))).all()
    assert rows == []
```

- [ ] **Step 2: Run the tests to confirm they fail on import**

```bash
cd backend
python3 -m pytest tests/test_seed_admin.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.startup'`.

- [ ] **Step 3: Implement the seed helper**

Create `backend/app/startup.py`:

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.base import async_session_factory
from app.db.models import User, UserRole

logger = logging.getLogger(__name__)


async def seed_initial_admin(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
) -> None:
    cfg = settings or get_settings()
    if not cfg.initial_admin_email or not cfg.initial_admin_password:
        return

    existing = await session.scalar(select(User).where(User.email == cfg.initial_admin_email))
    if existing is not None:
        logger.info("seed_skipped existing_admin=%s", cfg.initial_admin_email)
        return

    session.add(
        User(
            email=cfg.initial_admin_email,
            password_hash=hash_password(cfg.initial_admin_password),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    await session.flush()
    logger.info("seed_created admin=%s", cfg.initial_admin_email)


@asynccontextmanager
async def lifespan(app: FastAPI):
    factory = async_session_factory()
    async with factory() as session:
        await seed_initial_admin(session)
        await session.commit()
    yield
```

- [ ] **Step 4: Wire the lifespan into the FastAPI app factory**

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
python3 -m pytest tests/test_seed_admin.py -v
```

Expected: all four tests pass.

- [ ] **Step 6: Run the full backend test suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: all tests pass (51 total). The lifespan-wrapped `create_app()` used by other test fixtures runs the seed once with default empty env, so no admin row leaks across tests.

- [ ] **Step 7: Commit**

```bash
git add backend/app/startup.py backend/app/main.py backend/tests/test_seed_admin.py
git commit -m "feat: add lifespan hook seeding initial admin from env"
```

---

### Task 9: Admin CLI Tool

**Files:**
- Create: `backend/app/cli.py`
- Create: `backend/tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

Create `backend/tests/test_cli.py`:

```python
import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from app.cli import app as cli_app
from app.core.security import hash_password, verify_password
from app.db.models import User, UserRole


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
async def existing_user(db_session) -> User:
    user = User(
        email="dave@example.test",
        password_hash=hash_password("original-pwd-1234"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def test_create_user_inserts_row(runner: CliRunner) -> None:
    result = runner.invoke(
        cli_app,
        ["create-user", "new-user@example.test", "--password", "newpwd-1234"],
    )
    assert result.exit_code == 0, result.output

    import asyncio

    from app.db.base import async_session_factory

    async def _check() -> None:
        async with async_session_factory()() as session:
            user = await session.scalar(
                select(User).where(User.email == "new-user@example.test")
            )
            assert user is not None
            assert user.role == UserRole.USER
            assert verify_password(user.password_hash, "newpwd-1234")

    asyncio.run(_check())


def test_create_user_with_admin_flag(runner: CliRunner) -> None:
    result = runner.invoke(
        cli_app,
        [
            "create-user",
            "another-admin@example.test",
            "--password",
            "adminpwd-1234",
            "--admin",
        ],
    )
    assert result.exit_code == 0

    import asyncio

    from app.db.base import async_session_factory

    async def _check() -> None:
        async with async_session_factory()() as session:
            user = await session.scalar(
                select(User).where(User.email == "another-admin@example.test")
            )
            assert user is not None
            assert user.role == UserRole.ADMIN

    asyncio.run(_check())


def test_list_users_prints_seeded_user(runner: CliRunner, existing_user: User) -> None:
    result = runner.invoke(cli_app, ["list-users"])
    assert result.exit_code == 0
    assert "dave@example.test" in result.output


def test_set_active_disables_and_re_enables(runner: CliRunner, existing_user: User) -> None:
    disable = runner.invoke(cli_app, ["set-active", "dave@example.test", "--inactive"])
    assert disable.exit_code == 0

    import asyncio

    from app.db.base import async_session_factory

    async def _state(expected: bool) -> None:
        async with async_session_factory()() as session:
            user = await session.scalar(
                select(User).where(User.email == "dave@example.test")
            )
            assert user is not None
            assert user.is_active is expected

    asyncio.run(_state(False))

    enable = runner.invoke(cli_app, ["set-active", "dave@example.test"])
    assert enable.exit_code == 0
    asyncio.run(_state(True))


def test_reset_password_updates_hash(runner: CliRunner, existing_user: User) -> None:
    result = runner.invoke(
        cli_app,
        ["reset-password", "dave@example.test", "--password", "brand-new-1234"],
    )
    assert result.exit_code == 0

    import asyncio

    from app.db.base import async_session_factory

    async def _check() -> None:
        async with async_session_factory()() as session:
            user = await session.scalar(
                select(User).where(User.email == "dave@example.test")
            )
            assert user is not None
            assert verify_password(user.password_hash, "brand-new-1234")
            assert not verify_password(user.password_hash, "original-pwd-1234")

    asyncio.run(_check())
```

- [ ] **Step 2: Run the test to confirm it fails on import**

```bash
cd backend
python3 -m pytest tests/test_cli.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.cli'`.

- [ ] **Step 3: Implement the CLI**

Create `backend/app/cli.py`:

```python
import asyncio
from typing import Annotated

import typer
from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import async_session_factory
from app.db.models import User, UserRole

app = typer.Typer(help="KnowledgeDeck admin CLI", no_args_is_help=True)


def _warn_short_password(password: str) -> None:
    if len(password) < 8:
        typer.echo("warning: password shorter than 8 characters", err=True)


async def _create_user(email: str, password: str, *, admin: bool) -> None:
    async with async_session_factory()() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise typer.BadParameter(f"user already exists: {email}")
        session.add(
            User(
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN if admin else UserRole.USER,
                is_active=True,
            )
        )
        await session.commit()


@app.command("create-user")
def create_user(
    email: str,
    password: Annotated[
        str,
        typer.Option(
            prompt=True,
            hide_input=True,
            confirmation_prompt=True,
            help="Password for the new user. Will be prompted if omitted.",
        ),
    ],
    admin: Annotated[bool, typer.Option("--admin/--no-admin", help="Create as admin role.")] = False,
) -> None:
    _warn_short_password(password)
    asyncio.run(_create_user(email, password, admin=admin))
    role = "admin" if admin else "user"
    typer.echo(f"created {role}: {email}")


async def _list_users() -> list[User]:
    async with async_session_factory()() as session:
        rows = (await session.scalars(select(User).order_by(User.id))).all()
        return list(rows)


@app.command("list-users")
def list_users() -> None:
    rows = asyncio.run(_list_users())
    if not rows:
        typer.echo("(no users)")
        return
    typer.echo(f"{'id':>4}  {'email':40}  {'role':6}  {'active':6}  created_at")
    for u in rows:
        typer.echo(
            f"{u.id:>4}  {u.email:40}  {u.role.value:6}  {str(u.is_active):6}  {u.created_at.isoformat()}"
        )


async def _set_active(email: str, *, active: bool) -> None:
    async with async_session_factory()() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            raise typer.BadParameter(f"user not found: {email}")
        user.is_active = active
        await session.commit()


@app.command("set-active")
def set_active(
    email: str,
    inactive: Annotated[bool, typer.Option("--inactive", help="Disable instead of enable.")] = False,
) -> None:
    asyncio.run(_set_active(email, active=not inactive))
    typer.echo(f"{email} active={not inactive}")


async def _reset_password(email: str, password: str) -> None:
    async with async_session_factory()() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            raise typer.BadParameter(f"user not found: {email}")
        user.password_hash = hash_password(password)
        await session.commit()


@app.command("reset-password")
def reset_password(
    email: str,
    password: Annotated[
        str,
        typer.Option(
            prompt=True,
            hide_input=True,
            confirmation_prompt=True,
            help="New password. Will be prompted if omitted.",
        ),
    ],
) -> None:
    _warn_short_password(password)
    asyncio.run(_reset_password(email, password))
    typer.echo(f"reset password for {email}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run the CLI tests**

```bash
cd backend
python3 -m pytest tests/test_cli.py -v
```

Expected: all five tests pass.

- [ ] **Step 5: Run the full backend test suite**

```bash
cd backend
python3 -m pytest -v
```

Expected: all tests pass (56 total).

- [ ] **Step 6: Commit**

```bash
git add backend/app/cli.py backend/tests/test_cli.py
git commit -m "feat: add admin CLI for user management"
```

---

### Task 10: Backend Container Entrypoint Update

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update the backend Dockerfile**

Replace `backend/Dockerfile` contents with:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"

COPY app ./app
COPY alembic.ini ./alembic.ini

EXPOSE 8080

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080"]
```

The CMD chains migration and uvicorn so the database is on the latest schema before the app accepts requests.

- [ ] **Step 2: Verify docker-compose.yml does not need changes**

The existing `backend` service block already mounts the build context and reads `.env`. Inspect `docker-compose.yml` and confirm:
- `backend` service `build.context: ./backend` is unchanged.
- `env_file: - .env` is present (it is).

No edits required. Move to Step 3.

- [ ] **Step 3: Validate the Compose configuration still renders**

```bash
cp .env.example .env
docker compose --env-file .env.example config >/dev/null
docker compose --env-file .env.example --profile gpu config >/dev/null
echo "compose OK"
rm .env
```

Expected: `compose OK` printed; no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile
git commit -m "feat: run alembic upgrade in backend container entrypoint"
```

---

### Task 11: Frontend Test Setup and Auth Dependencies

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`

For the rest of the frontend tasks, run all `npm` commands using:

```bash
NODE_DIR=/homepool2/tobyleung/actions-runner/externals.2.330.0/node24/bin
NODE=$NODE_DIR/node
NPM="$NODE $NODE_DIR/../lib/node_modules/npm/bin/npm-cli.js"
PATH="$NODE_DIR:$PATH"
```

This is the verified Node 24 environment from the scaffold task.

- [ ] **Step 1: Update package.json with new dependencies and test scripts**

Replace `frontend/package.json` contents with:

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
    "jsdom": "^25.0.1",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 2: Add vitest configuration**

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

- [ ] **Step 3: Install the new dependencies**

```bash
cd frontend
$NPM install
```

Expected: `added N packages` summary. Should add axios, zustand, vitest, RTL, jsdom, @vitejs/plugin-react, etc.

- [ ] **Step 4: Smoke-test vitest with a trivial passing test**

Create `frontend/lib/__sanity.test.ts`:

```typescript
import { describe, expect, it } from "vitest";

describe("vitest sanity", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
```

Run:

```bash
cd frontend
$NPM test
```

Expected: 1 file, 1 test passed.

Then delete the sanity test file:

```bash
rm frontend/lib/__sanity.test.ts
```

- [ ] **Step 5: Run typecheck to confirm config is sound**

```bash
cd frontend
$NPM run typecheck
```

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/vitest.setup.ts
git commit -m "feat: add frontend test setup and auth deps"
```

---

### Task 12: Frontend Auth Store

**Files:**
- Create: `frontend/lib/auth-store.ts`
- Create: `frontend/lib/auth-store.test.ts`

- [ ] **Step 1: Write the failing auth store tests**

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
    const { token, user } = useAuthStore.getState();
    expect(token).toBeNull();
    expect(user).toBeNull();
  });

  it("setSession populates token and user", () => {
    useAuthStore.getState().setSession("jwt-abc", { id: 1, email: "a@b.c", role: "user" });
    const state = useAuthStore.getState();
    expect(state.token).toBe("jwt-abc");
    expect(state.user).toEqual({ id: 1, email: "a@b.c", role: "user" });
  });

  it("clearSession resets state", () => {
    useAuthStore.getState().setSession("jwt-abc", { id: 1, email: "a@b.c", role: "admin" });
    useAuthStore.getState().clearSession();
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
  });

  it("persists token to localStorage under knowledgedeck-auth", () => {
    useAuthStore.getState().setSession("jwt-xyz", { id: 7, email: "x@y.z", role: "user" });
    const raw = localStorage.getItem("knowledgedeck-auth");
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!).state.token).toBe("jwt-xyz");
  });
});
```

- [ ] **Step 2: Run the test to confirm failure**

```bash
cd frontend
$NPM test -- lib/auth-store.test.ts
```

Expected: cannot resolve `./auth-store`.

- [ ] **Step 3: Implement the auth store**

Create `frontend/lib/auth-store.ts`:

```typescript
"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type AuthUser = {
  id: number;
  email: string;
  role: "user" | "admin";
};

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

- [ ] **Step 4: Run the test to confirm pass**

```bash
cd frontend
$NPM test -- lib/auth-store.test.ts
```

Expected: 4 tests pass.

- [ ] **Step 5: Run the full frontend test + typecheck suite**

```bash
cd frontend
$NPM test && $NPM run typecheck
```

Expected: all tests pass; typecheck exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/auth-store.ts frontend/lib/auth-store.test.ts
git commit -m "feat: add frontend auth store with localStorage persistence"
```

---

### Task 13: Frontend Axios Instance with Interceptors

**Files:**
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/api.test.ts`

- [ ] **Step 1: Write the failing axios tests**

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
    vi.stubGlobal("location", { ...window.location, href: "http://localhost/", pathname: "/" });
  });

  afterEach(() => {
    mock.restore();
    vi.unstubAllGlobals();
  });

  it("attaches Bearer header when a token is set", async () => {
    useAuthStore.getState().setSession("jwt-abc", { id: 1, email: "a@b.c", role: "user" });
    mock.onGet("/echo").reply((config) => {
      return [200, { auth: config.headers?.Authorization ?? null }];
    });

    const response = await api.get("/echo");
    expect(response.data).toEqual({ auth: "Bearer jwt-abc" });
  });

  it("omits Authorization header when no token is set", async () => {
    mock.onGet("/echo").reply((config) => {
      return [200, { auth: config.headers?.Authorization ?? null }];
    });
    const response = await api.get("/echo");
    expect(response.data).toEqual({ auth: null });
  });

  it("clears session and redirects on 401", async () => {
    useAuthStore.getState().setSession("jwt-abc", { id: 1, email: "a@b.c", role: "user" });
    mock.onGet("/protected").reply(401, { detail: "invalid_token" });

    const replaceMock = vi.fn();
    vi.stubGlobal("location", {
      ...window.location,
      pathname: "/dashboard",
      replace: replaceMock,
      assign: vi.fn(),
    });

    await expect(api.get("/protected")).rejects.toThrow();
    expect(useAuthStore.getState().token).toBeNull();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });

  it("does not redirect when already on /login", async () => {
    useAuthStore.getState().setSession("jwt-abc", { id: 1, email: "a@b.c", role: "user" });
    mock.onPost("/auth/login").reply(401, { detail: "invalid_credentials" });

    const replaceMock = vi.fn();
    vi.stubGlobal("location", {
      ...window.location,
      pathname: "/login",
      replace: replaceMock,
      assign: vi.fn(),
    });

    await expect(api.post("/auth/login", {})).rejects.toThrow();
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
```

The test uses `axios-mock-adapter`. Add it to dev deps in this task:

```bash
cd frontend
$NPM install --save-dev axios-mock-adapter@^2.1.0
```

- [ ] **Step 2: Run the test to confirm failure**

```bash
cd frontend
$NPM test -- lib/api.test.ts
```

Expected: cannot resolve `./api`.

- [ ] **Step 3: Implement the axios instance**

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

- [ ] **Step 4: Run the api tests**

```bash
cd frontend
$NPM test -- lib/api.test.ts
```

Expected: 4 tests pass.

- [ ] **Step 5: Run the full frontend test + typecheck suite**

```bash
cd frontend
$NPM test && $NPM run typecheck
```

Expected: all tests pass; typecheck exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/api.ts frontend/lib/api.test.ts frontend/package.json frontend/package-lock.json
git commit -m "feat: add axios instance with bearer and 401 interceptors"
```

---

### Task 14: Frontend AuthGuard Component

**Files:**
- Create: `frontend/components/AuthGuard.tsx`
- Create: `frontend/components/AuthGuard.test.tsx`

- [ ] **Step 1: Write the failing AuthGuard tests**

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

  afterEach(() => {
    mock.restore();
  });

  it("redirects to /login when no token", async () => {
    render(
      <AuthGuard>
        <div>protected</div>
      </AuthGuard>,
    );
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("protected")).toBeNull();
  });

  it("renders children after /auth/me succeeds", async () => {
    useAuthStore.getState().setSession("jwt-abc", { id: 1, email: "a@b.c", role: "user" });
    mock.onGet("/auth/me").reply(200, {
      id: 1,
      email: "a@b.c",
      role: "user",
      is_active: true,
      created_at: "2026-04-25T10:00:00Z",
    });

    render(
      <AuthGuard>
        <div>protected</div>
      </AuthGuard>,
    );

    expect(await screen.findByText("protected")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("clears session and redirects when /auth/me returns 401", async () => {
    useAuthStore.getState().setSession("jwt-abc", { id: 1, email: "a@b.c", role: "user" });
    mock.onGet("/auth/me").reply(401, { detail: "invalid_token" });

    render(
      <AuthGuard>
        <div>protected</div>
      </AuthGuard>,
    );

    await waitFor(() => expect(useAuthStore.getState().token).toBeNull());
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });
});
```

- [ ] **Step 2: Run the test to confirm failure**

```bash
cd frontend
$NPM test -- components/AuthGuard.test.tsx
```

Expected: cannot resolve `./AuthGuard`.

- [ ] **Step 3: Implement AuthGuard**

Create `frontend/components/AuthGuard.tsx`:

```typescript
"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { api } from "../lib/api";
import { useAuthStore } from "../lib/auth-store";

type AuthGuardProps = { children: ReactNode };

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const setSession = useAuthStore((s) => s.setSession);
  const clearSession = useAuthStore((s) => s.clearSession);
  const [verified, setVerified] = useState(false);

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    api
      .get("/auth/me")
      .then((res) => {
        if (cancelled) return;
        setSession(token, {
          id: res.data.id,
          email: res.data.email,
          role: res.data.role,
        });
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
  }, [token, router, setSession, clearSession]);

  if (!verified) {
    return null;
  }
  return <>{children}</>;
}
```

- [ ] **Step 4: Run the AuthGuard tests**

```bash
cd frontend
$NPM test -- components/AuthGuard.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 5: Run the full frontend test + typecheck suite**

```bash
cd frontend
$NPM test && $NPM run typecheck
```

Expected: all tests pass; typecheck exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/AuthGuard.tsx frontend/components/AuthGuard.test.tsx
git commit -m "feat: add client-side AuthGuard component"
```

---

### Task 15: Login Page and Protected Route Group

**Files:**
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/login/page.test.tsx`
- Create: `frontend/app/(protected)/layout.tsx`
- Move: `frontend/app/page.tsx` → `frontend/app/(protected)/page.tsx`

- [ ] **Step 1: Write the failing login page tests**

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

  afterEach(() => {
    mock.restore();
  });

  it("submits credentials and stores session on success", async () => {
    mock.onPost("/auth/login").reply(200, {
      access_token: "jwt-abc",
      token_type: "bearer",
      expires_in: 28800,
      user: { id: 1, email: "a@b.c", role: "user" },
    });

    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/password/i), "hunter2hunter2");
    fireEvent.click(screen.getByRole("button", { name: /sign in|login/i }));

    await waitFor(() => expect(useAuthStore.getState().token).toBe("jwt-abc"));
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("shows the invalid_credentials error on 401", async () => {
    mock.onPost("/auth/login").reply(401, { detail: "invalid_credentials" });

    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    fireEvent.click(screen.getByRole("button", { name: /sign in|login/i }));

    expect(await screen.findByTestId("login-error")).toHaveAttribute(
      "data-error-key",
      "auth.error.invalid_credentials",
    );
    expect(useAuthStore.getState().token).toBeNull();
  });

  it("shows the account_disabled error on 403", async () => {
    mock.onPost("/auth/login").reply(403, { detail: "account_disabled" });

    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/password/i), "hunter2hunter2");
    fireEvent.click(screen.getByRole("button", { name: /sign in|login/i }));

    expect(await screen.findByTestId("login-error")).toHaveAttribute(
      "data-error-key",
      "auth.error.account_disabled",
    );
  });
});
```

- [ ] **Step 2: Run the test to confirm failure**

```bash
cd frontend
$NPM test -- app/login/page.test.tsx
```

Expected: cannot resolve `./page`.

- [ ] **Step 3: Implement the login page**

Create `frontend/app/login/page.tsx`:

```typescript
"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import axios, { isAxiosError } from "axios";

import { api } from "../../lib/api";
import { useAuthStore } from "../../lib/auth-store";

const ERROR_KEYS: Record<string, string> = {
  invalid_credentials: "auth.error.invalid_credentials",
  account_disabled: "auth.error.account_disabled",
  network: "auth.error.network",
};

export default function LoginPage() {
  const router = useRouter();
  const setSession = useAuthStore((s) => s.setSession);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErrorKey(null);
    setSubmitting(true);
    try {
      const res = await api.post<{
        access_token: string;
        user: { id: number; email: string; role: "user" | "admin" };
      }>("/auth/login", { email, password });
      setSession(res.data.access_token, res.data.user);
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
          <label htmlFor="email" className="block text-sm">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="password" className="block text-sm">
            Password
          </label>
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
          <div
            data-testid="login-error"
            data-error-key={errorKey}
            className="text-sm text-red-600"
          >
            {errorKey}
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

// Re-exported for tests in environments without "next" runtime
export { axios };
```

(The trailing `export { axios }` makes `vi.mock` resolve cleanly without affecting runtime usage; it is dead-code at the page level and may be removed once unused warnings are introduced.)

- [ ] **Step 4: Move existing root page into protected route group**

Move file:

```bash
mkdir -p frontend/app/\(protected\)
git mv frontend/app/page.tsx frontend/app/\(protected\)/page.tsx
```

Add a logout button to `frontend/app/(protected)/page.tsx`. Edit the file: at the top, replace the imports and add a logout handler. Replace the entire file with:

```typescript
"use client";

import { FileText, LogOut, MessageSquare, Presentation, Search } from "lucide-react";
import { useRouter } from "next/navigation";

import { api } from "../../lib/api";
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

  async function handleLogout() {
    try {
      await api.post("/auth/logout");
    } catch {
      // best-effort: still clear local session even if server failed
    }
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
          <div className="mb-2 truncate" title={user?.email}>
            {user?.email ?? ""}
          </div>
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
                <button
                  className="rounded-md bg-foreground px-3 py-2 text-sm text-white"
                  type="button"
                >
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

- [ ] **Step 5: Run the login page tests**

```bash
cd frontend
$NPM test -- app/login/page.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 6: Run the full frontend test + typecheck suite**

```bash
cd frontend
$NPM test && $NPM run typecheck
```

Expected: all frontend tests pass; typecheck exit 0.

- [ ] **Step 7: Run the full backend test suite for a sanity check**

```bash
cd backend
python3 -m pytest -v
```

Expected: all backend tests still pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/app/login frontend/app/\(protected\)
git commit -m "feat: add login page, protected layout, and logout integration"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Implemented in |
|---|---|
| Settings additions (TTL 480, INITIAL_ADMIN_*, DATABASE_URL) | Task 1 |
| New backend deps (sqlalchemy, psycopg, alembic, argon2-cffi, pyjwt, email-validator, typer, testcontainers) | Task 1 |
| `users` and `login_logs` tables, indexes, `user_role` enum, CITEXT extension | Tasks 2, 3 |
| ORM models | Task 2 |
| Alembic config + initial migration + test fixture | Task 3 |
| `app/core/security.py` (argon2 hash/verify, JWT encode/decode, DUMMY_HASH) | Task 4 |
| `app/services/auth_service.py` (authenticate, open_login_log, close_latest_login_log, timing-safe path) | Task 5 |
| `get_current_user` / `get_current_admin` dependencies | Task 6 |
| `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | Task 7 |
| First admin auto-seed (idempotent, both env vars required) | Task 8 |
| CLI commands `create-user` / `list-users` / `set-active` / `reset-password` | Task 9 |
| Backend container entrypoint runs `alembic upgrade head` before uvicorn | Task 10 |
| Frontend deps (axios, zustand) + vitest test setup | Task 11 |
| Zustand auth store with `localStorage` persist | Task 12 |
| Axios instance + Bearer interceptor + 401 redirect | Task 13 |
| `AuthGuard` client component | Task 14 |
| `/login` page + `(protected)` route group + logout button | Task 15 |
| Error code contract (`invalid_credentials`, `account_disabled`, `invalid_token`, `user_not_found`, `admin_required`) | Tasks 6, 7, 15 |
| Email case-insensitivity (CITEXT) | Task 3 (migration), tested in Tasks 5, 7 |
| Timing-attack mitigation via DUMMY_HASH | Tasks 4, 5 |

**2. Placeholder scan:** no `TBD`, `TODO`, "implement later", "add appropriate error handling", or "similar to Task N" present in the plan body.

**3. Type consistency:**
- `User`, `LoginLog`, `UserRole`, `AuthUser`, `LoginRequest`, `LoginResponse`, `MeResponse` are spelled identically wherever referenced.
- Function names `authenticate`, `open_login_log`, `close_latest_login_log`, `seed_initial_admin`, `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`, `get_current_user`, `get_current_admin`, `setSession`, `clearSession` are consistent across tasks.
- Error code strings (`invalid_credentials`, `account_disabled`, `invalid_token`, `user_not_found`, `admin_required`) are consistent across backend and frontend.
- Port numbers, JWT TTL (480 minutes / 28800 seconds), and CITEXT/INET types are consistent.
