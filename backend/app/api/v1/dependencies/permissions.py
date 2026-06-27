"""RBAC dependency helpers — role checks on authenticated endpoints."""
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends

from app.api.v1.dependencies.auth import AuthRequired, CurrentUser
from app.core.errors import PermissionDenied
from app.db.session import ReadSession
from app.services.auth.mfa_enforcement import assert_mfa_enrolled


def require_roles(*allowed_roles: str) -> Callable[..., CurrentUser]:
    """Require the current user to hold at least one of the given roles."""

    async def _checker(current_user: AuthRequired, session: ReadSession) -> CurrentUser:
        if not any(role in current_user.roles for role in allowed_roles):
            raise PermissionDenied(
                message="You do not have permission to perform this action.",
            )
        await assert_mfa_enrolled(session, current_user.user_id, current_user.roles)
        return current_user

    return _checker


PublisherRequired = Annotated[CurrentUser, Depends(require_roles("data_publisher", "org_admin"))]
StewardRequired = Annotated[
    CurrentUser,
    Depends(require_roles("data_steward", "org_admin")),
]
AdminRequired = Annotated[CurrentUser, Depends(require_roles("org_admin"))]
ApproverRequired = Annotated[
    CurrentUser,
    Depends(require_roles("org_admin")),
]
DeveloperRequired = Annotated[CurrentUser, Depends(require_roles("developer", "org_admin"))]
