"""JWT claim helpers for OIDC access tokens."""

from __future__ import annotations

import base64
import json
from typing import Any

_STAFF_ROLE_MAP: dict[str, str] = {
    "data_publisher": "publisher",
    "data_steward": "steward",
    "org_admin": "admin",
    "developer": "developer",
}

_PRIORITY = ("org_admin", "data_steward", "developer", "data_publisher")


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode JWT payload without signature verification (token from IdP exchange)."""
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    padding = "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(parts[1] + padding)
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def extract_roles_and_staff_role(access_token: str) -> tuple[list[str], str]:
    """Map Keycloak realm roles to OpenCivic staff role for the portal shell."""
    claims = decode_jwt_payload(access_token)
    realm_roles = claims.get("realm_access", {})
    roles: list[str] = []
    if isinstance(realm_roles, dict):
        raw = realm_roles.get("roles", [])
        if isinstance(raw, list):
            roles = [str(role) for role in raw]

    staff_role = "publisher"
    for priority_role in _PRIORITY:
        if priority_role in roles:
            mapped = _STAFF_ROLE_MAP.get(priority_role)
            if mapped:
                staff_role = mapped
                break
    return roles, staff_role
