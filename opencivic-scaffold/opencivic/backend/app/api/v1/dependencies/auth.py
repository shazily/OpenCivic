"""Auth dependencies. RULE: tenant_id ALWAYS from validated JWT — never from client."""
import uuid
from typing import Annotated
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.errors import AuthenticationRequired, PermissionDenied

bearer_scheme = HTTPBearer(auto_error=False)

class CurrentUser:
    def __init__(self, user_id: uuid.UUID, tenant_id: uuid.UUID, roles: list[str]):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.roles = roles

async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    if not credentials:
        raise AuthenticationRequired(message="Authentication required.")
    # JWT validation via Keycloak JWKS — see core/security.py
    # tenant_id extracted from validated JWT claim — never from request body
    # Stub for scaffold — full implementation in Phase 2
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    roles = ["data_publisher"]
    request.state.tenant_id = tenant_id
    request.state.user_id = user_id
    return CurrentUser(user_id=user_id, tenant_id=tenant_id, roles=roles)

async def get_current_user_optional(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> "CurrentUser | None":
    if not credentials:
        return None
    try:
        return await get_current_user(request, credentials)
    except Exception:
        return None

AuthRequired = Annotated[CurrentUser, Depends(get_current_user)]
AuthOptional = Annotated["CurrentUser | None", Depends(get_current_user_optional)]
