"""Keycloak refresh-token session index for SCIM revoke."""

import json
import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.auth.keycloak_session_index import (
    register_keycloak_refresh,
    revoke_keycloak_sessions_for_user,
    unregister_keycloak_refresh,
)


@pytest.mark.asyncio
async def test_register_and_revoke_keycloak_refresh_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored: dict[str, str] = {}
    user_id = uuid.uuid4()
    token_a = "refresh-token-a"
    token_b = "refresh-token-b"
    revoked: list[str] = []

    async def fake_cache_get(key: str) -> str | None:
        return stored.get(key)

    async def fake_cache_set(key: str, value: str, ttl_seconds: int = 0) -> None:
        stored[key] = value

    async def fake_cache_delete(key: str) -> None:
        stored.pop(key, None)

    mock_client = AsyncMock()
    mock_client.revoke_refresh_token = AsyncMock(side_effect=lambda token: revoked.append(token))

    monkeypatch.setattr("app.services.auth.keycloak_session_index.cache_get", fake_cache_get)
    monkeypatch.setattr("app.services.auth.keycloak_session_index.cache_set", fake_cache_set)
    monkeypatch.setattr("app.services.auth.keycloak_session_index.cache_delete", fake_cache_delete)
    monkeypatch.setattr(
        "app.services.auth.keycloak_session_index.KeycloakTokenClient",
        lambda: mock_client,
    )

    await register_keycloak_refresh(user_id, token_a)
    await register_keycloak_refresh(user_id, token_b)
    await register_keycloak_refresh(user_id, token_a)

    count = await revoke_keycloak_sessions_for_user(user_id)
    assert count == 2
    assert set(revoked) == {token_a, token_b}
    assert f"keycloak:refresh:user:{user_id}" not in stored


@pytest.mark.asyncio
async def test_revoke_keycloak_sessions_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_cache_get(_key: str) -> str | None:
        return None

    monkeypatch.setattr("app.services.auth.keycloak_session_index.cache_get", fake_cache_get)
    count = await revoke_keycloak_sessions_for_user(uuid.uuid4())
    assert count == 0


@pytest.mark.asyncio
async def test_unregister_keycloak_refresh_keeps_other_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored: dict[str, str] = {}
    user_id = uuid.uuid4()

    async def fake_cache_get(key: str) -> str | None:
        return stored.get(key)

    async def fake_cache_set(key: str, value: str, ttl_seconds: int = 0) -> None:
        stored[key] = value

    async def fake_cache_delete(key: str) -> None:
        stored.pop(key, None)

    monkeypatch.setattr("app.services.auth.keycloak_session_index.cache_get", fake_cache_get)
    monkeypatch.setattr("app.services.auth.keycloak_session_index.cache_set", fake_cache_set)
    monkeypatch.setattr("app.services.auth.keycloak_session_index.cache_delete", fake_cache_delete)

    await register_keycloak_refresh(user_id, "token-a")
    await register_keycloak_refresh(user_id, "token-b")
    await unregister_keycloak_refresh(user_id, "token-a")

    key = f"keycloak:refresh:user:{user_id}"
    assert key in stored
    remaining = json.loads(stored[key])
    assert remaining == ["token-b"]

    await unregister_keycloak_refresh(user_id, "token-b")
    assert key not in stored
