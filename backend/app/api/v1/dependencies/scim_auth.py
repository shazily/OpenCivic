"""SCIM webhook token verification."""

from fastapi import Header

from app.core.config import settings
from app.core.errors import AuthenticationRequired


def require_scim_token(x_scim_token: str | None = Header(default=None, alias="X-SCIM-Token")) -> None:
    """Validate the SCIM provisioning token."""
    secret = settings.SCIM_WEBHOOK_SECRET
    if not secret or x_scim_token != secret:
        raise AuthenticationRequired(message="Invalid SCIM webhook token.")
