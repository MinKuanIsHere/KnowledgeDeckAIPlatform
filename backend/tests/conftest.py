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
        await setup.execute(text(
            "TRUNCATE TABLE files, knowledge_bases, users RESTART IDENTITY CASCADE"
        ))
        await setup.commit()

    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


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


@pytest.fixture()
async def http_client():
    """ASGI test client backed by a fresh app instance per test."""
    from app.main import create_app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
