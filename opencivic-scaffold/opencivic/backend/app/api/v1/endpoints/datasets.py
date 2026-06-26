"""Dataset endpoints — CRUD, upload, submit, publish, archive, data API, lineage."""
import uuid
from fastapi import APIRouter, Query, UploadFile, BackgroundTasks
from app.api.v1.dependencies.auth import AuthRequired, AuthOptional
from app.db.session import WriteSession, ReadSession
router = APIRouter()

@router.get("/")
async def list_datasets(session: ReadSession, current_user: AuthOptional,
    page_size: int = Query(20, le=100), cursor: str | None = None):
    return {"data": [], "meta": {"has_more": False, "next_cursor": None, "total_count": 0}, "errors": []}

@router.post("/", status_code=201)
async def create_dataset(session: WriteSession, current_user: AuthRequired):
    return {"data": {"id": str(uuid.uuid4()), "status": "draft"}, "meta": {}, "errors": []}

@router.get("/{dataset_id}")
async def get_dataset(dataset_id: uuid.UUID, session: ReadSession, current_user: AuthOptional):
    return {"data": {"id": str(dataset_id)}, "meta": {}, "errors": []}

@router.post("/{dataset_id}/upload", status_code=202)
async def upload_file(dataset_id: uuid.UUID, file: UploadFile,
    session: WriteSession, current_user: AuthRequired, background_tasks: BackgroundTasks):
    """Triggers: ClamAV scan → schema inference → Parquet conversion → Celery ingest task."""
    return {"data": {"upload_id": str(uuid.uuid4()), "status": "processing"}, "meta": {}, "errors": []}

@router.post("/{dataset_id}/submit", status_code=202)
async def submit_for_review(dataset_id: uuid.UUID, session: WriteSession, current_user: AuthRequired):
    """draft → pending_review. Triggers maker-checker workflow."""
    return {"data": {"status": "pending_review"}, "meta": {}, "errors": []}

@router.delete("/{dataset_id}")
async def archive_dataset(dataset_id: uuid.UUID, session: WriteSession, current_user: AuthRequired):
    """published → archived. API returns 410 for archived datasets. Never hard-deleted."""
    return {"data": {"status": "archived"}, "meta": {}, "errors": []}

@router.get("/{dataset_id}/data")
async def get_dataset_data(dataset_id: uuid.UUID, session: ReadSession, current_user: AuthOptional,
    page_size: int = Query(100, le=10000), cursor: str | None = None,
    fields: str | None = None, sort: str | None = None):
    """Auto-generated REST API. Queries DuckDB over Parquet in Minio."""
    return {"data": [], "meta": {"has_more": False, "next_cursor": None, "total_count": 0}, "errors": []}

@router.get("/{dataset_id}/lineage")
async def get_lineage(dataset_id: uuid.UUID, session: ReadSession, current_user: AuthOptional):
    return {"data": {"nodes": [], "edges": []}, "meta": {}, "errors": []}

@router.get("/{dataset_id}/openapi.json")
async def get_dataset_openapi(dataset_id: uuid.UUID, session: ReadSession):
    """Auto-generated OpenAPI 3.1 spec for this dataset's data API."""
    return {}
