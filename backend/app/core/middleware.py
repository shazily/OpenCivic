"""OpenCivic — FastAPI HTTP middleware: request ID, tenant context, security headers.

Uses function-based middleware instead of BaseHTTPMiddleware to avoid Starlette
request-body deadlocks on POST/PATCH (encode/starlette#919).
"""

import uuid

import structlog
from fastapi import FastAPI, Request
from starlette.responses import Response

from app.core.rate_limit_middleware import edge_rate_limit_middleware

logger = structlog.get_logger(__name__)


async def request_id_middleware(request: Request, call_next) -> Response:
    """Attach a unique request ID to every request and response."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


async def tenant_context_middleware(request: Request, call_next) -> Response:
    """Extract tenant slug from subdomain and attach to request state."""
    host = request.headers.get("host", "")
    parts = host.split(".")
    if len(parts) >= 3:
        request.state.tenant_slug = parts[0]
    else:
        request.state.tenant_slug = None
    return await call_next(request)


async def security_headers_middleware(request: Request, call_next) -> Response:
    """Add security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def register_http_middlewares(app: FastAPI) -> None:
    """Register custom HTTP middleware (last registered runs first on the request)."""
    app.middleware("http")(security_headers_middleware)
    app.middleware("http")(edge_rate_limit_middleware)
    app.middleware("http")(request_id_middleware)
    app.middleware("http")(tenant_context_middleware)
