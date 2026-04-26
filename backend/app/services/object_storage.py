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
            # Attempt-then-ignore is race-safe under concurrent worker startup,
            # unlike check-then-act which would let a second worker fail with
            # BucketAlreadyOwnedByYou after both passed bucket_exists().
            try:
                self._client.make_bucket(self._bucket)
            except S3Error as e:
                if e.code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                    raise

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
    """Process-wide MinioClient. Tests replace `_client` directly via conftest.

    Not thread-safe for first-call initialization. Safe in practice because
    the lifespan (single-threaded asyncio context) calls this before any
    request handlers run, so `_client` is already set by the time worker
    threads or background tasks could reach it.
    """
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
