"""Governance CSV export endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_governance_export_requires_steward(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/api/v1/workflow/governance/export", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_governance_export_csv_for_steward(client: AsyncClient) -> None:
    import os

    token = os.environ.get("OPENCIVIC_STEWARD_AUTH_TOKEN") or os.environ["OPENCIVIC_DEV_AUTH_TOKEN"]
    response = await client.get(
        "/api/v1/workflow/governance/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["format"] == "csv"
    assert payload["filename"] == "governance-summary-30d.csv"
    assert "metric,value" in payload["content"]
    assert "pending_review" in payload["content"]


@pytest.mark.asyncio
async def test_governance_export_respects_days_filter(client: AsyncClient) -> None:
    import os

    token = os.environ.get("OPENCIVIC_STEWARD_AUTH_TOKEN") or os.environ["OPENCIVIC_DEV_AUTH_TOKEN"]
    response = await client.get(
        "/api/v1/workflow/governance/export?days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["filename"] == "governance-summary-7d.csv"
    assert payload["report_days"] == 7
    assert "report_days,7" in payload["content"]
