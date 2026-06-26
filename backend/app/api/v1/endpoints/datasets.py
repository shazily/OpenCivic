"""Dataset endpoints — CRUD, upload, submit, publish, archive, data API, lineage."""

import hashlib
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.core.errors import ValidationError

from app.api.v1.dependencies.auth import AuthOptional
from app.api.v1.dependencies.permissions import PublisherRequired, StewardRequired
from app.core.config import settings
from app.db.session import ReadSession, WriteSession
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.dataset_version_repository import DatasetVersionRepository
from app.repositories.lineage_repository import LineageRepository
from app.schemas.dataset import (
    DatasetChatRequest,
    DatasetCreate,
    DatasetDataListResponse,
    DatasetListResponse,
    DatasetResponse,
    DatasetUpdate,
    DownloadRecordRequest,
    EmbargoScheduleRequest,
    PaginationMeta,
    UploadResponse,
    UploadResponseData,
    UploadSessionCreate,
    TusSessionCreate,
    TusSessionResponseData,
)
from app.schemas.lineage import LineageEdgeResponse, LineageGraphResponse, LineageNodeResponse
from app.schemas.workflow import SubmitForReviewRequest, WorkflowSubmissionResponse
from app.services.analytics.usage_service import record_usage_event
from app.services.data.dataset_data_reader import DatasetDataReader
from app.services.events.event_publisher import EventPublisher
from app.services.governance.workflow_service import WorkflowService
from app.services.ingest.upload_validation import raw_storage_key, validate_upload_file
from app.services.storage.storage_client import get_storage_client
from app.workers.tasks.tasks import process_upload

router = APIRouter()


def _dataset_to_response(dataset: object) -> DatasetResponse:
    return DatasetResponse.model_validate(dataset)


def _schedule_usage(
    background_tasks: BackgroundTasks,
    *,
    tenant_id: uuid.UUID,
    dataset_id: uuid.UUID,
    event_type: str,
    actor_id: uuid.UUID | None = None,
    format_name: str | None = None,
) -> None:
    background_tasks.add_task(
        record_usage_event,
        tenant_id=tenant_id,
        dataset_id=dataset_id,
        event_type=event_type,
        actor_id=actor_id,
        format_name=format_name,
    )


@router.get("/")
async def list_datasets(
    session: ReadSession,
    current_user: AuthOptional,
    page_size: int = Query(20, le=100),
    cursor: str | None = None,
    filter_status: str | None = Query(None, alias="filter[status]"),
    filter_tag: str | None = Query(None, alias="filter[tag]"),
    filter_publisher: str | None = Query(None, alias="filter[publisher_id]"),
    sort: str | None = None,
    mine: bool = False,
) -> DatasetListResponse:
    """List datasets. Anonymous callers only see published public datasets (RLS + default filter)."""
    effective_status = filter_status
    if current_user is None:
        effective_status = "published"

    publisher_id = None
    if mine and current_user is not None:
        publisher_id = current_user.user_id
    elif filter_publisher and current_user is not None:
        publisher_id = uuid.UUID(filter_publisher)

    repo = DatasetRepository(session)
    default_sort = "-published_at" if effective_status == "published" else "-created_at"
    items, has_more, next_cursor, total_count = await repo.list_datasets(
        page_size=page_size,
        cursor=cursor,
        status=effective_status,
        tag=filter_tag,
        sort=sort or default_sort,
        publisher_id=publisher_id,
    )
    return DatasetListResponse(
        data=[_dataset_to_response(item) for item in items],
        meta=PaginationMeta(
            has_more=has_more,
            next_cursor=next_cursor,
            total_count=total_count,
        ),
    )


@router.post("/", status_code=201)
async def create_dataset(
    body: DatasetCreate,
    session: WriteSession,
    current_user: PublisherRequired,
) -> dict:
    repo = DatasetRepository(session)
    dataset = await repo.create(
        tenant_id=current_user.tenant_id,
        publisher_id=current_user.user_id,
        data=body,
    )
    await EventPublisher.publish(
        session,
        tenant_id=current_user.tenant_id,
        event_type="DatasetCreated",
        aggregate_id=dataset.id,
        aggregate_type="dataset",
        actor_id=current_user.user_id,
        payload={"title": dataset.title, "slug": dataset.slug, "status": dataset.status},
    )
    return {
        "data": _dataset_to_response(dataset).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.get("/facets/tags")
async def dataset_tag_facets(
    session: ReadSession,
    current_user: AuthOptional,
    limit: int = Query(30, le=100),
) -> dict:
    """Published dataset tag facets for the public catalog filter UI."""
    del current_user
    facets = await DatasetRepository(session).published_tag_facets(limit=limit)
    return {
        "data": facets,
        "meta": {"total_count": len(facets)},
        "errors": [],
    }


@router.get("/upload/tus-config")
async def tus_upload_config(current_user: PublisherRequired) -> dict:
    """Return TUS resumable upload endpoint when the tusd profile is enabled."""
    del current_user
    if not settings.TUS_ENABLED:
        return {
            "data": {"enabled": False, "endpoint": None},
            "meta": {},
            "errors": [],
        }
    return {
        "data": {
            "enabled": True,
            "endpoint": settings.TUS_URL.rstrip("/") + "/",
            "max_size_bytes": settings.UPLOAD_MAX_BYTES,
            "allowed_extensions": settings.allowed_upload_extensions,
        },
        "meta": {},
        "errors": [],
    }


@router.post("/{dataset_id}/upload/tus-session", status_code=201)
async def create_tus_upload_session(
    dataset_id: uuid.UUID,
    body: TusSessionCreate,
    session: WriteSession,
    current_user: PublisherRequired,
) -> dict:
    """Prepare TUS upload metadata and storage key for the browser tus-js-client."""
    from app.services.ingest.upload_validation import extension_from_filename

    if not settings.TUS_ENABLED:
        raise ValidationError(message="TUS uploads are not enabled.", field="tus")

    repo = DatasetRepository(session)
    await repo.get_for_publisher(dataset_id, current_user.user_id)
    extension = extension_from_filename(body.filename)
    upload_id = uuid.uuid4()
    storage_key = raw_storage_key(
        current_user.tenant_id,
        dataset_id,
        upload_id,
        extension,
    )
    payload = TusSessionResponseData(
        endpoint=settings.TUS_URL.rstrip("/") + "/",
        storage_key=storage_key,
        upload_metadata={
            "filename": body.filename,
            "filetype": extension,
            "tenant_id": str(current_user.tenant_id),
            "dataset_id": str(dataset_id),
            "storage_key": storage_key,
            "publisher_id": str(current_user.user_id),
        },
    )
    return {
        "data": payload.model_dump(),
        "meta": {},
        "errors": [],
    }


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: uuid.UUID,
    session: ReadSession,
    current_user: AuthOptional,
    background_tasks: BackgroundTasks,
) -> dict:
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if dataset.status == "published":
        _schedule_usage(
            background_tasks,
            tenant_id=dataset.tenant_id,
            dataset_id=dataset.id,
            event_type="view",
            actor_id=current_user.user_id if current_user else None,
        )
    return {
        "data": _dataset_to_response(dataset).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.patch("/{dataset_id}")
async def update_dataset(
    dataset_id: uuid.UUID,
    body: DatasetUpdate,
    session: WriteSession,
    current_user: PublisherRequired,
) -> dict:
    """Update dataset metadata while in draft or changes_requested state."""
    repo = DatasetRepository(session)
    dataset = await repo.get_for_publisher(dataset_id, current_user.user_id)
    if dataset.status not in {"draft", "changes_requested"}:
        raise ValidationError(
            message="Metadata can only be edited while the dataset is a draft or has changes requested.",
            field="status",
        )
    updated = await repo.update_metadata(dataset, data=body)
    await EventPublisher.publish(
        session,
        tenant_id=current_user.tenant_id,
        event_type="DatasetMetadataUpdated",
        aggregate_id=updated.id,
        aggregate_type="dataset",
        actor_id=current_user.user_id,
        payload={"title": updated.title, "status": updated.status},
    )
    return {
        "data": _dataset_to_response(updated).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.post("/{dataset_id}/upload", status_code=202)
async def upload_file(
    dataset_id: uuid.UUID,
    file: UploadFile,
    session: WriteSession,
    current_user: PublisherRequired,
) -> UploadResponse:
    """Accept a CSV/TSV upload, store raw bytes in object storage, and enqueue ingest."""
    repo = DatasetRepository(session)
    await repo.get_for_publisher(dataset_id, current_user.user_id)

    content = await file.read()
    extension = validate_upload_file(file, content)
    upload_id = uuid.uuid4()
    storage_key = raw_storage_key(
        current_user.tenant_id,
        dataset_id,
        upload_id,
        extension,
    )

    storage = get_storage_client()
    await storage.ensure_bucket(settings.MINIO_BUCKET)
    content_type = file.content_type or (
        "text/tab-separated-values" if extension == "tsv" else "text/csv"
    )
    await storage.put(storage_key, content, content_type=content_type)

    idempotency_key = hashlib.sha256(
        f"upload:{dataset_id}:{storage_key}".encode()
    ).hexdigest()
    task = process_upload.delay(
        str(current_user.tenant_id),
        str(dataset_id),
        storage_key,
        file.filename or f"upload.{extension}",
        idempotency_key,
        str(current_user.user_id),
    )

    return UploadResponse(
        data=UploadResponseData(
            job_id=task.id,
            storage_key=storage_key,
            status="queued",
        ),
    )


@router.post("/{dataset_id}/upload/sessions", status_code=201)
async def create_upload_session(
    dataset_id: uuid.UUID,
    body: UploadSessionCreate,
    session: WriteSession,
    current_user: PublisherRequired,
) -> dict:
    """Start a resumable chunked upload session."""
    from app.services.ingest.chunked_upload_service import CHUNK_SIZE_BYTES, ChunkedUploadService
    from app.services.ingest.upload_validation import extension_from_filename

    repo = DatasetRepository(session)
    await repo.get_for_publisher(dataset_id, current_user.user_id)
    extension = extension_from_filename(body.filename)
    upload_session = await ChunkedUploadService().create_session(
        tenant_id=current_user.tenant_id,
        dataset_id=dataset_id,
        publisher_id=current_user.user_id,
        filename=body.filename,
        extension=extension,
        total_size=body.total_size,
    )
    return {
        "data": {
            "session_id": str(upload_session.session_id),
            "chunk_size": CHUNK_SIZE_BYTES,
            "total_chunks": upload_session.total_chunks,
            "total_size": upload_session.total_size,
        },
        "meta": {},
        "errors": [],
    }


@router.put("/{dataset_id}/upload/sessions/{session_id}/chunks/{chunk_index}", status_code=200)
async def upload_chunk(
    dataset_id: uuid.UUID,
    session_id: uuid.UUID,
    chunk_index: int,
    session: WriteSession,
    current_user: PublisherRequired,
    file: UploadFile,
) -> dict:
    """Upload one chunk for a resumable session."""
    from app.services.ingest.chunked_upload_service import ChunkedUploadService

    repo = DatasetRepository(session)
    await repo.get_for_publisher(dataset_id, current_user.user_id)
    content = await file.read()
    upload_session = await ChunkedUploadService().store_chunk(
        tenant_id=current_user.tenant_id,
        session_id=session_id,
        chunk_index=chunk_index,
        content=content,
    )
    return {
        "data": {
            "session_id": str(upload_session.session_id),
            "chunk_index": chunk_index,
            "received_chunks": upload_session.received_chunks,
            "total_chunks": upload_session.total_chunks,
        },
        "meta": {},
        "errors": [],
    }


@router.post("/{dataset_id}/upload/sessions/{session_id}/complete", status_code=202)
async def complete_upload_session(
    dataset_id: uuid.UUID,
    session_id: uuid.UUID,
    session: WriteSession,
    current_user: PublisherRequired,
) -> UploadResponse:
    """Merge uploaded chunks and enqueue ingest."""
    from app.services.ingest.chunked_upload_service import ChunkedUploadService

    repo = DatasetRepository(session)
    await repo.get_for_publisher(dataset_id, current_user.user_id)
    storage_key, filename = await ChunkedUploadService().complete_session(
        tenant_id=current_user.tenant_id,
        session_id=session_id,
    )
    idempotency_key = hashlib.sha256(
        f"upload:{dataset_id}:{storage_key}".encode()
    ).hexdigest()
    task = process_upload.delay(
        str(current_user.tenant_id),
        str(dataset_id),
        storage_key,
        filename,
        idempotency_key,
        str(current_user.user_id),
    )
    return UploadResponse(
        data=UploadResponseData(
            job_id=task.id,
            storage_key=storage_key,
            status="queued",
        ),
    )


@router.post("/{dataset_id}/submit", status_code=202)
async def submit_for_review(
    dataset_id: uuid.UUID,
    body: SubmitForReviewRequest,
    session: WriteSession,
    current_user: PublisherRequired,
) -> dict:
    """Submit an ingested dataset draft for steward review."""
    repo = DatasetRepository(session)
    await repo.get_for_publisher(dataset_id, current_user.user_id)
    service = WorkflowService(session, current_user.tenant_id)
    submission = await service.submit(dataset_id, current_user.user_id, body.notes)
    return {
        "data": WorkflowSubmissionResponse.model_validate(submission).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.post("/{dataset_id}/schedule", status_code=202)
async def schedule_embargo(
    dataset_id: uuid.UUID,
    body: EmbargoScheduleRequest,
    session: WriteSession,
    current_user: StewardRequired,
) -> dict:
    """Schedule dataset publication at a future datetime (embargo)."""
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if dataset.status not in {"pending_review", "pending_approval"}:
        raise ValidationError(
            message="Only datasets awaiting review can be scheduled for embargo publication.",
            field="status",
        )
    embargo_until = body.embargo_until
    if embargo_until.tzinfo is None:
        embargo_until = embargo_until.replace(tzinfo=UTC)
    if embargo_until <= datetime.now(UTC):
        raise ValidationError(
            message="Embargo datetime must be in the future.",
            field="embargo_until",
        )
    service = WorkflowService(session, current_user.tenant_id)
    await service.schedule(dataset_id, embargo_until, current_user.user_id)
    dataset = await repo.get_by_id(dataset_id)
    return {
        "data": _dataset_to_response(dataset).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.delete("/{dataset_id}")
async def archive_dataset(
    dataset_id: uuid.UUID,
    session: WriteSession,
    current_user: PublisherRequired,
) -> dict:
    """Archive a published dataset."""
    repo = DatasetRepository(session)
    await repo.get_for_publisher(dataset_id, current_user.user_id)
    service = WorkflowService(session, current_user.tenant_id)
    dataset = await service.archive(dataset_id, current_user.user_id)
    return {
        "data": _dataset_to_response(dataset).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.get("/{dataset_id}/data")
async def get_dataset_data(
    dataset_id: uuid.UUID,
    session: ReadSession,
    current_user: AuthOptional,
    background_tasks: BackgroundTasks,
    page_size: int = Query(100, le=10000),
    cursor: str | None = None,
    fields: str | None = None,
    sort: str | None = None,
) -> DatasetDataListResponse:
    """Return paginated rows from the latest Parquet snapshot."""
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if dataset.status == "published":
        _schedule_usage(
            background_tasks,
            tenant_id=dataset.tenant_id,
            dataset_id=dataset.id,
            event_type="api_call",
            actor_id=current_user.user_id if current_user else None,
        )
    reader = DatasetDataReader(session)
    rows, has_more, next_cursor, total_count, _version_number = await reader.read_page(
        dataset_id,
        page_size=page_size,
        cursor=cursor,
        fields=fields,
        sort=sort,
    )
    return DatasetDataListResponse(
        data=rows,
        meta=PaginationMeta(
            has_more=has_more,
            next_cursor=next_cursor,
            total_count=total_count,
        ),
        errors=[],
    )


@router.get("/{dataset_id}/lineage")
async def get_lineage(
    dataset_id: uuid.UUID,
    session: ReadSession,
    current_user: AuthOptional,
) -> dict:
    """Return W3C PROV-style lineage graph for a dataset."""
    from app.db.session import set_tenant_context

    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)
    lineage_repo = LineageRepository(session)
    nodes, edges = await lineage_repo.get_graph_for_dataset(dataset_id)
    graph = LineageGraphResponse(
        nodes=[LineageNodeResponse.model_validate(node) for node in nodes],
        edges=[LineageEdgeResponse.model_validate(edge) for edge in edges],
    )
    return {"data": graph.model_dump(mode="json"), "meta": {}, "errors": []}


@router.post("/{dataset_id}/download", status_code=202)
async def record_download(
    dataset_id: uuid.UUID,
    body: DownloadRecordRequest,
    session: ReadSession,
    current_user: AuthOptional,
    background_tasks: BackgroundTasks,
) -> dict:
    """Record a dataset download event (called by client after file generation)."""
    from app.db.session import set_tenant_context

    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)
    if dataset.status != "published":
        raise HTTPException(status_code=404, detail="Dataset is not published.")
    _schedule_usage(
        background_tasks,
        tenant_id=dataset.tenant_id,
        dataset_id=dataset.id,
        event_type="download",
        actor_id=current_user.user_id if current_user else None,
        format_name=body.format,
    )
    return {
        "data": {"dataset_id": str(dataset_id), "format": body.format, "recorded": True},
        "meta": {},
        "errors": [],
    }


@router.post("/{dataset_id}/chat", status_code=200)
async def chat_dataset(
    dataset_id: uuid.UUID,
    body: DatasetChatRequest,
    session: ReadSession,
    current_user: AuthOptional,
    background_tasks: BackgroundTasks,
) -> dict:
    """Ask a natural-language question about published dataset data."""
    from app.db.session import set_tenant_context
    from app.services.ai.chat_service import chat_with_dataset

    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)
    if dataset.status != "published":
        raise HTTPException(status_code=404, detail="Dataset is not published.")

    result = await chat_with_dataset(
        session,
        dataset_id,
        body.question,
        user_id=current_user.user_id if current_user else None,
    )
    _schedule_usage(
        background_tasks,
        tenant_id=dataset.tenant_id,
        dataset_id=dataset.id,
        event_type="ai_query",
        actor_id=current_user.user_id if current_user else None,
    )
    return {"data": result, "meta": {}, "errors": []}


@router.post("/{dataset_id}/suggest-metadata", status_code=200)
async def suggest_metadata(
    dataset_id: uuid.UUID,
    session: ReadSession,
    current_user: PublisherRequired,
) -> dict:
    """Suggest DCAT-3 metadata (AI-assisted when enabled, heuristic otherwise)."""
    repo = DatasetRepository(session)
    dataset = await repo.get_for_publisher(dataset_id, current_user.user_id)
    from app.services.ai.metadata_service import suggest_dataset_metadata

    suggestions = await suggest_dataset_metadata(dataset, user_id=current_user.user_id)
    return {"data": suggestions, "meta": {}, "errors": []}


@router.get("/{dataset_id}/download-url")
async def get_download_url(
    dataset_id: uuid.UUID,
    session: ReadSession,
    current_user: AuthOptional,
    format: str = Query("parquet", pattern=r"^(parquet|csv|json)$"),
    expires_in: int = Query(3600, le=86400),
) -> dict:
    """Return a pre-signed URL for direct download from object storage (large files)."""
    from app.db.session import set_tenant_context

    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)
    if dataset.status != "published":
        raise HTTPException(status_code=404, detail="Dataset is not published.")

    version = await DatasetVersionRepository(session).get_latest(dataset_id)
    if version is None or not version.storage_path:
        raise HTTPException(status_code=404, detail="No downloadable snapshot available.")

    storage = get_storage_client()
    url = await storage.presign_get(version.storage_path, expires_in=expires_in)
    return {
        "data": {
            "url": url,
            "format": format,
            "expires_in": expires_in,
            "version_number": version.version_number,
        },
        "meta": {},
        "errors": [],
    }


@router.get("/{dataset_id}/openapi.json")
async def get_dataset_openapi(
    dataset_id: uuid.UUID,
    session: ReadSession,
    current_user: AuthOptional,
) -> dict:
    """Return auto-generated OpenAPI 3.1 spec for this dataset's data API."""
    from app.db.session import set_tenant_context
    from app.services.api.dataset_openapi import build_dataset_openapi

    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)
    if dataset.status != "published":
        raise HTTPException(status_code=404, detail="OpenAPI is only available for published datasets.")
    spec = build_dataset_openapi(dataset)
    return {"data": spec, "meta": {}, "errors": []}


@router.get("/{dataset_id}/odata")
async def get_dataset_odata_service(
    dataset_id: uuid.UUID,
    session: ReadSession,
    current_user: AuthOptional,
) -> dict:
    """OData 4.0 service root stub for a published dataset."""
    from app.db.session import set_tenant_context
    from app.services.api.dataset_openapi import DEFAULT_API_BASE

    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)
    if dataset.status != "published":
        raise HTTPException(status_code=404, detail="OData is only available for published datasets.")

    service_root = f"{DEFAULT_API_BASE.rstrip('/')}/api/v1/datasets/{dataset_id}/odata"
    entity_set = dataset.slug.replace("-", "_")
    return {
        "data": {
            "odata_version": "4.0",
            "service_root": service_root,
            "entity_set": entity_set,
            "metadata_url": f"{service_root}/$metadata",
            "example_filter": f"{service_root}/{entity_set}?$top=100",
        },
        "meta": {},
        "errors": [],
    }


@router.get("/{dataset_id}/odata/$metadata")
async def get_dataset_odata_metadata(
    dataset_id: uuid.UUID,
    session: ReadSession,
    current_user: AuthOptional,
) -> Response:
    """OData 4.0 CSDL $metadata XML stub for a published dataset."""
    from app.db.session import set_tenant_context
    from app.services.api.dataset_openapi import DEFAULT_API_BASE
    from app.services.api.odata_metadata import build_odata_metadata_xml

    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)
    if dataset.status != "published":
        raise HTTPException(status_code=404, detail="OData metadata is only available for published datasets.")

    service_root = f"{DEFAULT_API_BASE.rstrip('/')}/api/v1/datasets/{dataset_id}/odata"
    xml = build_odata_metadata_xml(dataset, service_root=service_root)
    return Response(content=xml, media_type="application/xml")


@router.get("/{dataset_id}/odata/{entity_set}/$count")
async def get_dataset_odata_count(
    dataset_id: uuid.UUID,
    entity_set: str,
    session: ReadSession,
    current_user: AuthOptional,
) -> dict:
    """OData $count stub for a published dataset entity set."""
    from app.db.session import set_tenant_context
    from app.services.api.dataset_openapi import DEFAULT_API_BASE
    from app.services.api.odata_entity import build_odata_count_payload, normalize_entity_set_name

    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)
    if dataset.status != "published":
        raise HTTPException(status_code=404, detail="OData is only available for published datasets.")
    if entity_set != normalize_entity_set_name(dataset):
        raise HTTPException(status_code=404, detail="Entity set not found.")

    count = int(dataset.row_count or 0)
    service_root = f"{DEFAULT_API_BASE.rstrip('/')}/api/v1/datasets/{dataset_id}/odata"
    payload = build_odata_count_payload(count=count)
    payload["@odata.context"] = f"{service_root}/$metadata#{entity_set}/$count"
    return {"data": payload, "meta": {}, "errors": []}


@router.get("/{dataset_id}/odata/{entity_set}")
async def get_dataset_odata_entity_set(
    dataset_id: uuid.UUID,
    entity_set: str,
    session: ReadSession,
    current_user: AuthOptional,
    top: int = Query(100, alias="$top", ge=1, le=1000),
    skip: int = Query(0, alias="$skip", ge=0),
) -> dict:
    """OData entity set JSON collection for a published dataset."""
    from app.core.errors import DatasetDataNotAvailable
    from app.db.session import set_tenant_context
    from app.services.api.dataset_openapi import DEFAULT_API_BASE
    from app.services.api.odata_entity import (
        build_odata_entity_payload,
        normalize_entity_set_name,
    )

    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)
    if dataset.status != "published":
        raise HTTPException(status_code=404, detail="OData is only available for published datasets.")
    if entity_set != normalize_entity_set_name(dataset):
        raise HTTPException(status_code=404, detail="Entity set not found.")

    service_root = f"{DEFAULT_API_BASE.rstrip('/')}/api/v1/datasets/{dataset_id}/odata"
    try:
        reader = DatasetDataReader(session)
        rows, _, _, total_count, _ = await reader.read_page(
            dataset_id,
            page_size=top,
            cursor=str(skip) if skip else None,
            fields=None,
            sort=None,
        )
    except DatasetDataNotAvailable:
        rows = []
        total_count = int(dataset.row_count or 0)

    payload = build_odata_entity_payload(
        service_root=service_root,
        entity_set=entity_set,
        rows=rows,
        total_count=total_count,
    )
    return {"data": payload, "meta": {}, "errors": []}


@router.get("/{dataset_id}/connector")
async def get_dataset_connector_status(
    dataset_id: uuid.UUID,
    session: ReadSession,
    current_user: AuthOptional,
) -> dict:
    """Linked connector sync status for a dataset (public metadata only)."""
    from app.db.session import set_tenant_context
    from app.repositories.connector_repository import ConnectorRepository

    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)

    connector = await ConnectorRepository(session).get_by_dataset_id(dataset_id)
    if connector is None:
        return {"data": None, "meta": {}, "errors": []}

    return {
        "data": {
            "id": str(connector.id),
            "name": connector.name,
            "type": connector.type,
            "status": connector.status,
            "circuit_state": connector.circuit_state,
            "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
            "next_sync_at": connector.next_sync_at.isoformat() if connector.next_sync_at else None,
            "sync_frequency": connector.sync_frequency,
        },
        "meta": {},
        "errors": [],
    }
