"""Developer console API — API keys CRUD."""

import uuid

from fastapi import APIRouter, status

from app.api.v1.dependencies.permissions import DeveloperRequired
from app.db.session import ReadSession, WriteSession
from app.repositories.api_key_repository import ApiKeyRepository
from app.schemas.api_key import ApiKeyCreateRequest, ApiKeyCreatedResponse, ApiKeyResponse

router = APIRouter()


@router.get("/")
async def list_api_keys(
    session: ReadSession,
    current_user: DeveloperRequired,
) -> dict:
    """List API keys for the authenticated developer."""
    repo = ApiKeyRepository(session)
    items = await repo.list_for_owner(current_user.user_id)
    return {
        "data": [
            ApiKeyResponse.model_validate(item).model_dump(mode="json") for item in items
        ],
        "meta": {"total_count": len(items), "owner_id": str(current_user.user_id)},
        "errors": [],
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreateRequest,
    session: WriteSession,
    current_user: DeveloperRequired,
) -> dict:
    """Create an API key. Raw key is returned once — store it securely."""
    repo = ApiKeyRepository(session)
    api_key, raw_key = await repo.create(
        tenant_id=current_user.tenant_id,
        owner_id=current_user.user_id,
        name=body.name,
        scopes=body.scopes,
        expires_at=body.expires_at,
    )
    payload = ApiKeyCreatedResponse.model_validate(api_key).model_dump(mode="json")
    payload["raw_key"] = raw_key
    return {
        "data": payload,
        "meta": {},
        "errors": [],
    }


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: uuid.UUID,
    session: WriteSession,
    current_user: DeveloperRequired,
) -> dict:
    """Revoke an API key immediately."""
    repo = ApiKeyRepository(session)
    api_key = await repo.revoke(key_id, current_user.user_id)
    return {
        "data": ApiKeyResponse.model_validate(api_key).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.get("/sdk-snippets")
async def sdk_snippets(current_user: DeveloperRequired) -> dict:
    """Static SDK starter snippets."""
    base = "/api/v1"
    return {
        "data": {
            "python": (
                "import httpx\n"
                f'BASE = "{base}"\n'
                'headers = {"Authorization": "Bearer YOUR_API_KEY"}\n'
                'datasets = httpx.get(f"{BASE}/datasets/", headers=headers).json()["data"]\n'
            ),
            "javascript": (
                f'const BASE = "{base}";\n'
                'const headers = { Authorization: "Bearer YOUR_API_KEY" };\n'
                'const res = await fetch(`${BASE}/datasets/`, { headers });\n'
                'const datasets = (await res.json()).data;\n'
            ),
            "curl": f'curl -H "Authorization: Bearer YOUR_API_KEY" {base}/datasets/',
        },
        "meta": {},
        "errors": [],
    }
