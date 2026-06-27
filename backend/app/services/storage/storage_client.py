"""
OpenCivic — Storage client abstraction.
RULE: All application code uses StorageClient — never boto3/azure SDK directly.
Switch between Minio, S3, Azure, GCS via STORAGE_PROVIDER env var.
Large downloads use pre-signed URLs — never stream through FastAPI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class StorageClient(ABC):
    @abstractmethod
    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload bytes. Returns the storage key."""

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Download bytes by key."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete object by key."""

    @abstractmethod
    async def presign_get(self, key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed GET URL. Use for large file downloads — bypass FastAPI."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""

    @abstractmethod
    async def ensure_bucket(self, bucket: str) -> None:
        """Create bucket if it does not exist."""


class MinioStorageClient(StorageClient):
    """Minio/S3-compatible storage. Used for selfhosted and airgap deployments."""

    def _client(self):
        import boto3

        return boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name="us-east-1",
        )

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        import asyncio

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client().put_object(
                Bucket=settings.MINIO_BUCKET, Key=key, Body=data, ContentType=content_type
            ),
        )
        return key

    async def get(self, key: str) -> bytes:
        import asyncio

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, lambda: self._client().get_object(Bucket=settings.MINIO_BUCKET, Key=key)
        )
        return resp["Body"].read()

    async def delete(self, key: str) -> None:
        import asyncio

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: self._client().delete_object(Bucket=settings.MINIO_BUCKET, Key=key)
        )

    async def presign_get(self, key: str, expires_in: int = 3600) -> str:
        import asyncio

        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None,
            lambda: self._client().generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.MINIO_BUCKET, "Key": key},
                ExpiresIn=expires_in,
            ),
        )
        return url

    async def exists(self, key: str) -> bool:
        import asyncio

        from botocore.exceptions import ClientError

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None, lambda: self._client().head_object(Bucket=settings.MINIO_BUCKET, Key=key)
            )
            return True
        except ClientError:
            return False

    async def ensure_bucket(self, bucket: str) -> None:
        import asyncio

        from botocore.exceptions import ClientError

        loop = asyncio.get_event_loop()
        client = self._client()

        def _ensure() -> None:
            try:
                client.head_bucket(Bucket=bucket)
            except ClientError:
                client.create_bucket(Bucket=bucket)

        await loop.run_in_executor(None, _ensure)


def get_storage_client() -> StorageClient:
    """Factory — returns the configured storage client."""
    if settings.STORAGE_PROVIDER in ("minio", "s3"):
        return MinioStorageClient()
    raise NotImplementedError(f"Storage provider {settings.STORAGE_PROVIDER} not yet implemented.")


# Storage key conventions
def raw_upload_key(tenant_id: str, dataset_id: str, filename: str) -> str:
    return f"tenants/{tenant_id}/datasets/{dataset_id}/raw/{filename}"


def parquet_key(tenant_id: str, dataset_id: str, version: int) -> str:
    return f"tenants/{tenant_id}/datasets/{dataset_id}/versions/{version}/data.parquet"


def export_cache_key(tenant_id: str, dataset_id: str, format: str) -> str:
    return f"tenants/{tenant_id}/datasets/{dataset_id}/exports/latest.{format}"
