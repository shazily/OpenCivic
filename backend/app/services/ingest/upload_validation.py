"""Upload file validation for CSV/TSV ingest."""

import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import FileTooLarge, InvalidFileFormat

_ALLOWED_MIME_TYPES = {
    "text/csv",
    "text/tab-separated-values",
    "application/csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/json",
    "application/x-ndjson",
    "application/jsonl",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
    "application/x-parquet",
    "application/pdf",
}


def allowed_extensions() -> set[str]:
    """Configured file extensions without leading dots."""
    return {
        extension.strip().lower()
        for extension in settings.ALLOWED_UPLOAD_EXTENSIONS.split(",")
        if extension.strip()
    }


def extension_from_filename(filename: str) -> str:
    """Extract and validate the upload file extension."""
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in allowed_extensions():
        raise InvalidFileFormat(
            message="Only CSV, TSV, JSON, JSONL, XLS, XLSX, Parquet, and PDF files are supported.",
            field="file",
        )
    return extension


def validate_upload_file(file: UploadFile, content: bytes) -> str:
    """Validate upload size, extension, and MIME type. Returns normalized extension."""
    if not file.filename:
        raise InvalidFileFormat(message="Filename is required.", field="file")

    extension = extension_from_filename(file.filename)

    if len(content) > settings.UPLOAD_MAX_BYTES:
        raise FileTooLarge(
            message=f"File exceeds maximum size of {settings.UPLOAD_MAX_BYTES} bytes.",
            field="file",
        )

    if file.content_type and file.content_type not in _ALLOWED_MIME_TYPES:
        raise InvalidFileFormat(
            message="Unsupported file content type.",
            field="file",
        )

    return extension


def raw_storage_key(
    tenant_id: uuid.UUID,
    dataset_id: uuid.UUID,
    upload_id: uuid.UUID,
    extension: str,
) -> str:
    """Object storage key for a raw uploaded file."""
    return f"raw/{tenant_id}/{dataset_id}/{upload_id}.{extension}"
