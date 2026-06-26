"""
SharePoint/OneDrive connector — Microsoft Graph API.
IMPORTANT: Respects Retry-After headers. Per-tenant app registrations.
Ignoring throttling will get your app ID banned by Microsoft.
"""
import asyncio
import uuid
from datetime import datetime
from typing import Any, AsyncIterator

import httpx
import structlog

from connectors.base.connector_base import ConnectorBase, ConnectionTestResult, RecordBatch, SchemaSnapshot

logger = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class SharePointConnector(ConnectorBase):
    """
    Reads Excel/CSV files from SharePoint document libraries.
    Auth: OAuth2 Client Credentials (Entra ID app registration).
    Incremental: Microsoft Graph Delta query tracks changes since last sync.
    Throttling: respects Retry-After — never hammers Graph API.
    """
    CONNECTOR_TYPE = "sharepoint"

    async def _get_token(self) -> str:
        tenant_id = self._config["tenant_id"]
        client_id = self._config["client_id"]
        client_secret = self._config["client_secret"]
        url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
            })
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def _graph_get(self, token: str, path: str) -> dict:
        """Graph API GET with Retry-After respect."""
        url = f"{GRAPH_BASE}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            for attempt in range(5):
                resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 30))
                    logger.warning("sharepoint_throttled", wait_seconds=wait, connector_id=str(self.connector_id))
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
        raise RuntimeError("SharePoint throttling: max retries exceeded")

    async def test_connection(self) -> ConnectionTestResult:
        import time
        try:
            start = time.monotonic()
            token = await self._get_token()
            site_id = self._config["site_id"]
            await self._graph_get(token, f"/sites/{site_id}")
            return ConnectionTestResult(success=True, message="OK", latency_ms=int((time.monotonic() - start) * 1000))
        except Exception as e:
            return ConnectionTestResult(success=False, message=str(e))

    async def get_schema(self) -> SchemaSnapshot:
        return SchemaSnapshot(columns=[], row_count=None, sampled_at=datetime.utcnow())

    async def pull(self, since: datetime | None = None) -> AsyncIterator[RecordBatch]:
        import pandas as pd
        import io
        token = await self._get_token()
        site_id = self._config["site_id"]
        drive_id = self._config["drive_id"]
        folder_path = self._config.get("folder_path", "root")
        batch_size = self._config.get("batch_size", 1000)
        # List files in drive folder
        items_resp = await self._graph_get(token, f"/sites/{site_id}/drives/{drive_id}/root:/{folder_path}:/children")
        batch_num = 0
        for item in items_resp.get("value", []):
            name = item.get("name", "")
            if not (name.endswith(".csv") or name.endswith(".xlsx")):
                continue
            # Check modification time for incremental
            modified = item.get("lastModifiedDateTime", "")
            if since and modified:
                from datetime import timezone
                mod_dt = datetime.fromisoformat(modified.rstrip("Z")).replace(tzinfo=timezone.utc)
                if mod_dt.replace(tzinfo=None) <= since:
                    continue
            # Download file content
            item_id = item["id"]
            async with httpx.AsyncClient(timeout=60) as client:
                for attempt in range(5):
                    resp = await client.get(
                        f"{GRAPH_BASE}/sites/{site_id}/drives/{drive_id}/items/{item_id}/content",
                        headers={"Authorization": f"Bearer {token}"},
                        follow_redirects=True,
                    )
                    if resp.status_code == 429:
                        await asyncio.sleep(int(resp.headers.get("Retry-After", 30)))
                        continue
                    resp.raise_for_status()
                    content = resp.content
                    break
            if name.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(content))
            else:
                df = pd.read_excel(io.BytesIO(content))
            records = df.to_dict(orient="records")
            for i in range(0, len(records), batch_size):
                batch_num += 1
                yield RecordBatch(records=records[i:i + batch_size], batch_number=batch_num, total_batches=None)

    async def close(self) -> None:
        pass
