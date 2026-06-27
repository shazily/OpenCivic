"""In-memory StorageClient for tests without Minio."""

from app.services.storage.storage_client import StorageClient


class MemoryStorageClient(StorageClient):
    """Dict-backed object storage for pytest."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        self.objects[key] = data
        return key

    async def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise KeyError(key)
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def presign_get(self, key: str, expires_in: int = 3600) -> str:
        return f"memory://{key}"

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def ensure_bucket(self, bucket: str) -> None:
        return None
