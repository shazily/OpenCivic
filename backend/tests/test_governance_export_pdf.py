"""Governance PDF export stub."""

import base64
import os

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_governance_export_pdf_for_steward(client: AsyncClient) -> None:
    token = os.environ.get("OPENCIVIC_STEWARD_AUTH_TOKEN") or os.environ["OPENCIVIC_DEV_AUTH_TOKEN"]
    response = await client.get(
        "/api/v1/workflow/governance/export?format=pdf&days=30",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["format"] == "pdf"
    assert payload["filename"] == "governance-summary-30d.pdf"
    raw = base64.b64decode(payload["content_base64"])
    assert raw.startswith(b"%PDF")
