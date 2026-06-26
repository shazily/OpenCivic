"""Per-client API rate limiting — Valkey-backed edge fallback when APISIX is not in path."""

from __future__ import annotations

import hashlib

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.services.auth.edge_rate_limit import consume_rate_limit, rate_limit_from_gateway_headers
from app.services.auth.gateway_headers import (
    GATEWAY_TRUST_HEADER,
    RATE_LIMIT_LIMIT_HEADER,
    RATE_LIMIT_REMAINING_HEADER,
    RATE_LIMIT_RESET_HEADER,
)

logger = structlog.get_logger(__name__)

_EXEMPT_PREFIXES = (
    "/api/v1/health",
    "/api/v1/docs",
    "/api/v1/redoc",
    "/api/v1/openapi.json",
    "/api/v1/internal",
)


def _client_fingerprint(request: Request) -> str:
    auth = request.headers.get("authorization", "").strip().lower()
    if auth:
        return hashlib.sha256(auth.encode()).hexdigest()[:24]
    client = request.client.host if request.client else "unknown"
    return hashlib.sha256(client.encode()).hexdigest()[:24]


class EdgeRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforce per-minute request limits using Valkey counters.
    Uses trusted gateway identity headers when EDGE_AUTH_ENABLED.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.EDGE_RATE_LIMIT_ENABLED:
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api/v1") or path.startswith(_EXEMPT_PREFIXES):
            return await call_next(request)

        tenant_id = None
        user_id = None
        api_key_id = None
        auth_type = None
        rate_limit_override = None

        if (
            settings.EDGE_AUTH_ENABLED
            and settings.GATEWAY_AUTH_SECRET
            and request.headers.get(GATEWAY_TRUST_HEADER) == settings.GATEWAY_AUTH_SECRET
        ):
            tenant_id, user_id, api_key_id, auth_type = rate_limit_from_gateway_headers(
                dict(request.headers)
            )

        decision = await consume_rate_limit(
            tenant_id=tenant_id,
            user_id=user_id,
            api_key_id=api_key_id,
            auth_type=auth_type,
            rate_limit_override=rate_limit_override,
            client_fingerprint=_client_fingerprint(request),
        )

        if not decision.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "data": None,
                    "errors": [
                        {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "API rate limit exceeded. Retry after one minute.",
                            "field": None,
                        }
                    ],
                    "meta": {},
                },
                headers=decision.as_headers(),
            )

        response = await call_next(request)
        response.headers[RATE_LIMIT_LIMIT_HEADER] = str(decision.limit)
        response.headers[RATE_LIMIT_REMAINING_HEADER] = str(decision.remaining)
        response.headers[RATE_LIMIT_RESET_HEADER] = str(decision.reset_epoch)
        return response
