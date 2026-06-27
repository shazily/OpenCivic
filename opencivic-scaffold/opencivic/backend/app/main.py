"""OpenCivic — FastAPI application entry point."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import OpenCivicError
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware, TenantContextMiddleware

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    logger.info("opencivic_startup", deployment_mode=settings.DEPLOYMENT_MODE, ai_mode=settings.AI_MODE)
    from app.db.session import verify_db_connection
    from app.core.cache import verify_cache_connection
    await verify_db_connection()
    await verify_cache_connection()
    logger.info("opencivic_ready")
    yield
    from app.db.session import engine
    await engine.dispose()
    logger.info("opencivic_shutdown")


def create_application() -> FastAPI:
    app = FastAPI(
        title="OpenCivic API",
        description="Enterprise open data portal — REST API",
        version=settings.VERSION,
        docs_url="/api/v1/docs" if settings.DOCS_ENABLED else None,
        redoc_url="/api/v1/redoc" if settings.DOCS_ENABLED else None,
        openapi_url="/api/v1/openapi.json" if settings.DOCS_ENABLED else None,
        lifespan=lifespan,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )
    app.add_middleware(TenantContextMiddleware)
    app.include_router(api_router, prefix="/api/v1")

    @app.exception_handler(OpenCivicError)
    async def opencivic_error_handler(request: Request, exc: OpenCivicError) -> JSONResponse:
        logger.warning("opencivic_error", code=exc.code, message=exc.message, status=exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={"data": None, "errors": [{"code": exc.code, "message": exc.message, "field": exc.field}], "meta": {}},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", error_type=type(exc).__name__, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"data": None, "errors": [{"code": "INTERNAL_ERROR", "message": "An unexpected error occurred.", "field": None}], "meta": {}},
        )

    return app


app = create_application()
