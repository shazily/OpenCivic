"""Governance summary API tests."""

import os

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_governance_summary_requires_steward(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/workflow/governance/summary", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_governance_summary_for_steward(client: AsyncClient) -> None:
    headers = {"Authorization": f"Bearer {os.environ['DEV_STEWARD_AUTH_TOKEN']}"}
    response = await client.get("/api/v1/workflow/governance/summary", headers=headers)
    assert response.status_code == 200
    body = response.json()["data"]
    assert "pending_review" in body
    assert "sla_breached" in body
    assert body.get("report_days") == 30
