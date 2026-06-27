"""Abbreviated TUS reachability smoke for verify_release --tus."""

import os

import httpx

from app.core.config import settings


async def verify_tus() -> None:
    if settings.TUS_ENABLED is not True and os.environ.get("TUS_ENABLED", "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        print("tus_verify_skipped")
        return

    base = settings.TUS_INTERNAL_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        response = await client.get(f"{base}/")
        response.raise_for_status()

    endpoint = settings.MINIO_ENDPOINT.rstrip("/")
    async with httpx.AsyncClient(timeout=10.0) as client:
        minio = await client.get(f"{endpoint}/minio/health/live")
        minio.raise_for_status()

    print("tus_verify_ok")
