"""Post-deploy smoke checks — exits non-zero on failure."""
import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

API_BASE = os.environ.get("OPENCIVIC_API_URL", "http://localhost:8100/api/v1")
GATEWAY_BASE = os.environ.get("OPENCIVIC_GATEWAY_URL", "")
DEV_TOKEN = os.environ.get("DEV_AUTH_TOKEN", "dev-local-token-change-me")
STEWARD_TOKEN = os.environ.get("DEV_STEWARD_AUTH_TOKEN", "dev-steward-token-change-me")
ADMIN_TOKEN = os.environ.get("DEV_ADMIN_AUTH_TOKEN", "dev-admin-token-change-me")
INGEST_TIMEOUT_SECONDS = int(os.environ.get("VERIFY_INGEST_TIMEOUT", "90"))
AUTH_HEADERS = {"Authorization": f"Bearer {DEV_TOKEN}"}
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


async def verify() -> None:
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        live = await client.get("/health/live")
        live.raise_for_status()
        assert live.json().get("status") == "ok"

        ready = await client.get("/health/ready")
        ready.raise_for_status()
        checks = ready.json().get("checks", {})
        assert checks.get("database") == "ok", checks
        assert checks.get("cache") == "ok", checks

        overview = await client.get("/admin/overview", headers=ADMIN_HEADERS)
        overview.raise_for_status()
        overview_data = overview.json()["data"]
        assert overview_data["health"]["database"] == "ok"
        assert overview_data["deployment_mode"] in {"selfhosted", "cloud", "airgap"}

        connectors_list = await client.get("/connectors/", headers=ADMIN_HEADERS)
        connectors_list.raise_for_status()
        assert "data" in connectors_list.json()

        slug = f"release-verify-{uuid.uuid4().hex[:8]}"
        created = await client.post(
            "/datasets/",
            headers=AUTH_HEADERS,
            json={"title": "Release verify", "slug": slug},
        )
        created.raise_for_status()
        dataset_id = created.json()["data"]["id"]

        listed = await client.get("/datasets/", headers=AUTH_HEADERS)
        listed.raise_for_status()
        ids = {item["id"] for item in listed.json()["data"]}
        assert dataset_id in ids

        fetched = await client.get(f"/datasets/{dataset_id}", headers=AUTH_HEADERS)
        fetched.raise_for_status()
        assert fetched.json()["data"]["slug"] == slug

        csv_bytes = b"name,value\nrelease,1\n"
        upload = await client.post(
            f"/datasets/{dataset_id}/upload",
            headers=AUTH_HEADERS,
            files={"file": ("release-verify.csv", csv_bytes, "text/csv")},
        )
        upload.raise_for_status()
        assert upload.status_code == 202

        row_count = None
        for _ in range(INGEST_TIMEOUT_SECONDS):
            polled = await client.get(f"/datasets/{dataset_id}", headers=AUTH_HEADERS)
            polled.raise_for_status()
            row_count = polled.json()["data"].get("row_count")
            if row_count:
                break
            await asyncio.sleep(1)

        if not row_count:
            raise AssertionError(
                f"Ingest did not complete within {INGEST_TIMEOUT_SECONDS}s — worker may be down"
            )

        assert row_count == 1
        data = await client.get(f"/datasets/{dataset_id}/data", headers=AUTH_HEADERS)
        data.raise_for_status()
        rows = data.json()["data"]
        assert len(rows) == 1
        assert rows[0]["name"] == "release"

        lineage = await client.get(f"/datasets/{dataset_id}/lineage", headers=AUTH_HEADERS)
        lineage.raise_for_status()
        lineage_body = lineage.json()["data"]
        assert isinstance(lineage_body.get("nodes"), list)
        assert len(lineage_body["nodes"]) >= 1

        submit = await client.post(
            f"/datasets/{dataset_id}/submit",
            headers=AUTH_HEADERS,
            json={"notes": "Release verify submit"},
        )
        submit.raise_for_status()
        submission_id = submit.json()["data"]["id"]

        steward_headers = {"Authorization": f"Bearer {STEWARD_TOKEN}"}
        review = await client.post(
            f"/workflow/{submission_id}/review",
            headers=steward_headers,
            json={"action": "approve", "notes": "Release verify approve"},
        )
        review.raise_for_status()
        assert review.json()["data"]["status"] == "published"

        search = await client.get(
            "/search/",
            params={"q": "Release verify"},
            headers=AUTH_HEADERS,
        )
        search.raise_for_status()
        search_ids = {item["id"] for item in search.json()["data"]}
        assert dataset_id in search_ids

    print("release_verify_ok")


async def verify_gateway(gateway_url: str) -> None:
    """Smoke health and edge-auth through nginx → APISIX."""
    base = gateway_url.rstrip("/")
    token = os.environ.get("DEV_AUTH_TOKEN", "dev-local-token-change-me")
    async with httpx.AsyncClient(timeout=30.0) as client:
        live = await client.get(f"{base}/api/v1/health/live")
        live.raise_for_status()
        assert live.json().get("status") == "ok"
        ready = await client.get(f"{base}/api/v1/health/ready")
        ready.raise_for_status()
        assert ready.json().get("checks", {}).get("database") == "ok"

        denied = await client.get(f"{base}/api/v1/users/me")
        assert denied.status_code == 401, "protected route should reject anonymous at gateway"

        profile = await client.get(
            f"{base}/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        profile.raise_for_status()
        assert profile.json()["data"]["email"]
    print("gateway_verify_ok")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post-deploy smoke checks")
    parser.add_argument(
        "--gateway-url",
        default=GATEWAY_BASE or None,
        help="Verify API health via nginx/APISIX gateway URL (e.g. http://127.0.0.1:8080)",
    )
    parser.add_argument(
        "--tus",
        action="store_true",
        help="Run abbreviated TUS smoke when TUS_ENABLED=true",
    )
    args = parser.parse_args()
    try:
        asyncio.run(verify())
        if args.gateway_url:
            asyncio.run(verify_gateway(args.gateway_url))
        if args.tus and os.environ.get("TUS_ENABLED", "").lower() in {"1", "true", "yes"}:
            from scripts.verify_tus_smoke import verify_tus  # noqa: PLC0415

            asyncio.run(verify_tus())
    except Exception as exc:
        print(f"release_verify_failed: {exc}", file=sys.stderr)
        sys.exit(1)
