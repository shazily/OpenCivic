"""API key persistence — SQLAlchemy ORM only."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.db.models import ApiKey
from app.services.auth.api_key_cache import invalidate_api_key_cache

ALLOWED_SCOPES = frozenset({"read", "write", "admin"})


def generate_api_key_material() -> tuple[str, str, str]:
    """Return (raw_key, key_hash, key_prefix)."""
    raw_key = f"oc_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:8]
    return raw_key, key_hash, key_prefix


class ApiKeyRepository:
    """Tenant-scoped API key CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_owner(self, owner_id: uuid.UUID) -> list[ApiKey]:
        result = await self._session.scalars(
            select(ApiKey)
            .where(ApiKey.owner_id == owner_id)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.all())

    async def get_for_owner(self, key_id: uuid.UUID, owner_id: uuid.UUID) -> ApiKey:
        key = await self._session.scalar(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.owner_id == owner_id)
        )
        if key is None:
            raise ValidationError(message="API key not found.", field="id")
        return key

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        owner_id: uuid.UUID,
        name: str,
        scopes: list[str],
        expires_at: datetime | None = None,
    ) -> tuple[ApiKey, str]:
        """Create key; returns model and raw key (shown once)."""
        invalid = [scope for scope in scopes if scope not in ALLOWED_SCOPES]
        if invalid:
            raise ValidationError(
                message=f"Invalid scopes: {', '.join(invalid)}",
                field="scopes",
            )
        raw_key, key_hash, key_prefix = generate_api_key_material()
        api_key = ApiKey(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            scopes=scopes or ["read"],
            owner_id=owner_id,
            expires_at=expires_at,
        )
        self._session.add(api_key)
        await self._session.flush()
        return api_key, raw_key

    async def revoke(self, key_id: uuid.UUID, owner_id: uuid.UUID) -> ApiKey:
        key = await self.get_for_owner(key_id, owner_id)
        if key.revoked_at is not None:
            return key
        now = datetime.now(UTC)
        await self._session.execute(
            update(ApiKey).where(ApiKey.id == key_id).values(revoked_at=now)
        )
        key.revoked_at = now
        await invalidate_api_key_cache(key.key_hash)
        return key
