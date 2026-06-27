"""SCIM webhook authentication — shared token or HMAC-SHA256 body signature."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Request

from app.core.config import settings
from app.core.errors import AuthenticationRequired


def _normalize_signature(value: str) -> str:
    trimmed = value.strip()
    if trimmed.lower().startswith("sha256="):
        return trimmed[7:].strip()
    return trimmed


def verify_scim_hmac(body: bytes, signature: str | None, secret: str) -> bool:
    """Validate HMAC-SHA256 hex digest of the raw request body."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = _normalize_signature(signature)
    return hmac.compare_digest(expected, provided)


async def verify_scim_webhook_request(request: Request, body: bytes) -> None:
    """
    Accept X-SCIM-Token (legacy) or X-SCIM-Signature HMAC over the raw body.

    At least one valid method is required when SCIM_WEBHOOK_SECRET is configured.
    """
    secret = settings.SCIM_WEBHOOK_SECRET
    if not secret:
        raise AuthenticationRequired(message="SCIM webhook is not configured.")

    token = request.headers.get("X-SCIM-Token")
    if token and hmac.compare_digest(token, secret):
        return

    signature = request.headers.get("X-SCIM-Signature")
    if verify_scim_hmac(body, signature, secret):
        return

    raise AuthenticationRequired(message="Invalid SCIM webhook credentials.")
