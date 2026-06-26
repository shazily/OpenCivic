"""Public catalog visibility tests — anonymous users see published datasets only."""

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.dependencies.auth import CurrentUser, get_current_user
from app.main import app

SAMPLE_CSV = b"name,value\nalpha,1\nbeta,2\n"
STEWARD_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")


@pytest.fixture
async def steward_user(db_session) -> uuid.UUID:
    from app.db.models import User
    from app.db.session import set_tenant_context

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    await set_tenant_context(db_session, tenant_id)
    existing = await db_session.scalar(select(User).where(User.id == STEWARD_USER_ID))
    if existing is None:
        db_session.add(
            User(
                id=STEWARD_USER_ID,
                tenant_id=tenant_id,
                keycloak_user_id="test-steward",
                email="steward@test.local",
                name="Test Steward",
                roles=["data_steward"],
            )
        )
        await db_session.commit()
    return STEWARD_USER_ID


@pytest.fixture
def memory_storage(monkeypatch: pytest.MonkeyPatch):
    from tests.fakes.memory_storage import MemoryStorageClient

    client = MemoryStorageClient()
    for target in (
        "app.services.storage.storage_client.get_storage_client",
        "app.api.v1.endpoints.datasets.get_storage_client",
        "app.services.ingest.ingest_service.get_storage_client",
        "app.services.data.dataset_data_reader.get_storage_client",
    ):
        monkeypatch.setattr(target, lambda: client)
    return client


@pytest.fixture
def stub_celery_delay(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, tuple] = {}

    class FakeAsyncResult:
        id = "test-job-id"

    def fake_delay(*args: object, **kwargs: object) -> FakeAsyncResult:
        captured["args"] = args
        return FakeAsyncResult()

    monkeypatch.setattr(
        "app.api.v1.endpoints.datasets.process_upload.delay",
        fake_delay,
    )
    return captured


async def _create_draft_dataset(
    client: AsyncClient,
    auth_headers: dict[str, str],
    title: str,
) -> str:
    slug = f"public-catalog-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": title, "slug": slug},
    )
    assert created.status_code == 201
    return created.json()["data"]["id"]


async def _publish_dataset(
    client: AsyncClient,
    auth_headers: dict[str, str],
    steward_user: uuid.UUID,
    dataset_id: str,
) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    submit = await client.post(
        f"/api/v1/datasets/{dataset_id}/submit",
        headers=auth_headers,
        json={"notes": "Ready"},
    )
    assert submit.status_code == 202
    submission_id = submit.json()["data"]["id"]

    async def steward_auth() -> CurrentUser:
        return CurrentUser(
            user_id=steward_user,
            tenant_id=tenant_id,
            roles=["data_steward"],
        )

    app.dependency_overrides[get_current_user] = steward_auth
    try:
        review = await client.post(
            f"/api/v1/workflow/{submission_id}/review",
            headers=auth_headers,
            json={"action": "approve", "notes": "Published"},
        )
        assert review.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_anonymous_list_excludes_drafts(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    draft_id = await _create_draft_dataset(client, auth_headers, "Draft only dataset")

    public_list = await client.get("/api/v1/datasets/")
    assert public_list.status_code == 200
    public_ids = {item["id"] for item in public_list.json()["data"]}
    assert draft_id not in public_ids
    for item in public_list.json()["data"]:
        assert item["status"] == "published"


@pytest.mark.asyncio
async def test_anonymous_list_includes_published(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    from datetime import UTC, datetime

    from app.db.models import Dataset
    from app.db.session import set_tenant_context

    dataset_id = await _create_draft_dataset(client, auth_headers, "Published catalog entry")
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    await set_tenant_context(db_session, tenant_id)
    dataset = await db_session.get(Dataset, uuid.UUID(dataset_id))
    assert dataset is not None
    dataset.status = "published"
    dataset.published_at = datetime.now(UTC)
    await db_session.commit()

    public_list = await client.get("/api/v1/datasets/")
    assert public_list.status_code == 200
    public_ids = {item["id"] for item in public_list.json()["data"]}
    assert dataset_id in public_ids


@pytest.mark.asyncio
async def test_authenticated_list_includes_drafts(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    draft_id = await _create_draft_dataset(client, auth_headers, "Publisher draft visible")

    authed_list = await client.get(
        "/api/v1/datasets/?filter[status]=draft&page_size=100",
        headers=auth_headers,
    )
    assert authed_list.status_code == 200
    authed_ids = {item["id"] for item in authed_list.json()["data"]}
    assert draft_id in authed_ids
