import io

import pytest

from app.features.knowledge_bases.services.object_storage import MinioClient, get_minio_client


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
