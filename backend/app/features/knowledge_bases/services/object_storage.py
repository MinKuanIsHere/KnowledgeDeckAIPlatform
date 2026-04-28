import asyncio
from pathlib import Path
from typing import BinaryIO

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
        from minio import Minio

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
            # Check-then-act: avoids `make_bucket` on an existing bucket. We
            # accept the (theoretical) multi-worker TOCTOU race because the
            # MVP runs a single uvicorn worker, and this is the only path
            # MinIO doesn't reject when the container hostname contains an
            # underscore (e.g. `knowledgedeck_minio`).
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

    async def get_object(self, key: str) -> bytes:
        def _impl() -> bytes:
            response = self._client.get_object(self._bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(_impl)

    async def delete_object(self, key: str) -> None:
        def _impl() -> None:
            from minio.error import S3Error

            try:
                self._client.remove_object(self._bucket, key)
            except S3Error as e:
                # NoSuchKey is fine — delete is idempotent for our purposes.
                if e.code != "NoSuchKey":
                    raise

        await asyncio.to_thread(_impl)


class LocalObjectStorageClient:
    """Single-machine local filesystem storage.

    Files are stored under:
      {local_storage_root}/{minio_bucket}/{key}
    """

    def __init__(self, *, root: str, bucket: str) -> None:
        self._root = Path(root)
        self._bucket = bucket
        self._base = self._root / bucket

    @property
    def bucket(self) -> str:
        return self._bucket

    async def ensure_bucket(self) -> None:
        await asyncio.to_thread(self._base.mkdir, parents=True, exist_ok=True)

    async def put_object(
        self,
        key: str,
        data: BinaryIO,
        length: int,
        content_type: str,
    ) -> None:
        # `content_type` kept for API compatibility with MinIO backend.
        _ = content_type

        def _impl() -> None:
            path = self._base / key
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = data.read(length)
            with path.open("wb") as f:
                f.write(payload)

        await asyncio.to_thread(_impl)

    async def get_object(self, key: str) -> bytes:
        def _impl() -> bytes:
            path = self._base / key
            with path.open("rb") as f:
                return f.read()

        return await asyncio.to_thread(_impl)

    async def delete_object(self, key: str) -> None:
        def _impl() -> None:
            path = self._base / key
            if path.exists():
                path.unlink()

        await asyncio.to_thread(_impl)


StorageClient = MinioClient | LocalObjectStorageClient
_client: StorageClient | None = None


def get_minio_client() -> StorageClient:
    """Process-wide object storage client.

    - storage_backend=minio -> MinioClient
    - storage_backend=local -> LocalObjectStorageClient

    Not thread-safe for first-call initialization. Safe in practice because
    the lifespan (single-threaded asyncio context) calls this before any
    request handlers run, so `_client` is already set by the time worker
    threads or background tasks could reach it.
    """
    global _client
    if _client is None:
        s = get_settings()
        if s.storage_backend == "local":
            _client = LocalObjectStorageClient(
                root=s.local_storage_root,
                bucket=s.minio_bucket,
            )
        else:
            _client = MinioClient(
                endpoint=s.minio_endpoint,
                access_key=s.minio_access_key,
                secret_key=s.minio_secret_key,
                bucket=s.minio_bucket,
                secure=s.minio_secure,
            )
    return _client
