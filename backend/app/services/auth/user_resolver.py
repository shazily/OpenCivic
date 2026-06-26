"""Map validated Keycloak JWT claims to platform CurrentUser via database lookup."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import CurrentUser
from app.core.config import settings
from app.core.errors import UserNotFound
from app.db.models import User

_PLATFORM_ROLES = frozenset(
    {
        "org_admin",
        "data_publisher",
        "data_steward",
        "developer",
        "viewer",
        "super_admin",
    }
)


def _roles_from_claims(claims: dict[str, object]) -> list[str]:
    realm_access = claims.get("realm_access")
    if not isinstance(realm_access, dict):
        return []
    raw_roles = realm_access.get("roles")
    if not isinstance(raw_roles, list):
        return []
    return [role for role in raw_roles if isinstance(role, str) and role in _PLATFORM_ROLES]


async def resolve_user_from_claims(
    session: AsyncSession,
    claims: dict[str, object],
) -> CurrentUser:
    """Resolve platform user from Keycloak JWT claims (email + tenant_id)."""
    email = claims.get("email")
    if not isinstance(email, str) or not email:
        raise UserNotFound(message="Token is missing a valid email claim.")

    tenant_raw = claims.get("tenant_id", settings.DEV_TENANT_ID)
    if not isinstance(tenant_raw, str):
        raise UserNotFound(message="Token is missing a valid tenant_id claim.")
    tenant_id = uuid.UUID(tenant_raw)

    user = await session.scalar(
        select(User).where(User.tenant_id == tenant_id, User.email == email)
    )
    if user is None:
        raise UserNotFound(message="No platform user found for this identity.")

    return CurrentUser(
        user_id=user.id,
        tenant_id=tenant_id,
        roles=_roles_from_claims(claims) or list(user.roles),
    )
