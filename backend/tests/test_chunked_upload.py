"""Chunked resumable upload tests."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.live
@pytest.mark.asyncio
async def test_chunked_upload_session_flow(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    slug = f"chunk-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Chunk Upload", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]
    content = b"col1,col2\n1,2\n3,4\n"
    session_response = await client.post(
        f"/api/v1/datasets/{dataset_id}/upload/sessions",
        headers=auth_headers,
        json={"filename": "sample.csv", "total_size": len(content)},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["data"]["session_id"]

    with patch("app.workers.tasks.tasks.process_upload.delay") as mock_delay:
        mock_delay.return_value = type("Task", (), {"id": "task-chunk-1"})()
        chunk_response = await client.put(
            f"/api/v1/datasets/{dataset_id}/upload/sessions/{session_id}/chunks/0",
            headers=auth_headers,
            files={"file": ("chunk.bin", content, "application/octet-stream")},
        )
        assert chunk_response.status_code == 200
        complete_response = await client.post(
            f"/api/v1/datasets/{dataset_id}/upload/sessions/{session_id}/complete",
            headers=auth_headers,
        )
    assert complete_response.status_code == 202
    assert complete_response.json()["data"]["status"] == "queued"
    mock_delay.assert_called_once()
