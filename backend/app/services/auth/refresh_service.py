"""Refresh token rotation and family tracking in Valkey."""

from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass

from app.core.cache import cache_delete, cache_get, cache_set
from app.core.config import settings
from app.core.errors import InvalidToken


@dataclass(frozen=True)
class RefreshSession:
    """Opaque refresh token session stored server-side."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    roles: list[str]
    family_id: str


class RefreshService:
    """Manage opaque refresh tokens — never stored in plaintext outside httpOnly cookies."""

    def __init__(self) -> None:
        self._ttl = settings.REFRESH_COOKIE_MAX_AGE_SECONDS

    def _session_key(self, token: str) -> str:
        return f"refresh:session:{token}"

    def _family_key(self, family_id: str) -> str:
        return f"refresh:family:{family_id}"

    def _user_families_key(self, user_id: uuid.UUID) -> str:
        return f"refresh:user:{user_id}"

    async def _register_family(self, user_id: uuid.UUID, family_id: str) -> None:
        key = self._user_families_key(user_id)
        raw = await cache_get(key)
        families: list[str] = json.loads(raw) if raw else []
        if family_id not in families:
            families.append(family_id)
            await cache_set(key, json.dumps(families), ttl_seconds=self._ttl)

    async def create_session(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        roles: list[str],
        family_id: str | None = None,
    ) -> tuple[str, str]:
        """Create a new refresh token and family. Returns (token, family_id)."""
        token = secrets.token_urlsafe(48)
        resolved_family = family_id or secrets.token_urlsafe(16)
        payload = json.dumps(
            {
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "roles": roles,
                "family_id": resolved_family,
            }
        )
        await cache_set(self._session_key(token), payload, ttl_seconds=self._ttl)
        await cache_set(self._family_key(resolved_family), token, ttl_seconds=self._ttl)
        await self._register_family(user_id, resolved_family)
        return token, resolved_family

    async def load_session(self, token: str) -> RefreshSession:
        raw = await cache_get(self._session_key(token))
        if not raw:
            raise InvalidToken(
                message="Refresh token is invalid or expired.",
                code="INVALID_REFRESH",
            )
        data = json.loads(raw)
        family_id = data["family_id"]
        active = await cache_get(self._family_key(family_id))
        if active != token:
            raise InvalidToken(
                message="Refresh token has been revoked.",
                code="REFRESH_TOKEN_REUSE",
            )
        return RefreshSession(
            user_id=uuid.UUID(data["user_id"]),
            tenant_id=uuid.UUID(data["tenant_id"]),
            roles=list(data["roles"]),
            family_id=family_id,
        )

    async def rotate(self, old_token: str) -> tuple[str, RefreshSession]:
        """Rotate refresh token; invalidates the previous token in the family."""
        session = await self.load_session(old_token)
        await cache_delete(self._session_key(old_token))
        new_token, _family = await self.create_session(
            user_id=session.user_id,
            tenant_id=session.tenant_id,
            roles=session.roles,
            family_id=session.family_id,
        )
        return new_token, session

    async def revoke_family(self, family_id: str) -> None:
        """Revoke all refresh tokens in a family (logout / stolen token)."""
        active = await cache_get(self._family_key(family_id))
        if active:
            await cache_delete(self._session_key(active))
        await cache_delete(self._family_key(family_id))

    async def revoke_user_sessions(self, user_id: uuid.UUID) -> int:
        """Revoke every refresh-token family registered for a user."""
        key = self._user_families_key(user_id)
        raw = await cache_get(key)
        if not raw:
            return 0
        families: list[str] = json.loads(raw)
        for family_id in families:
            await self.revoke_family(family_id)
        await cache_delete(key)
        return len(families)
