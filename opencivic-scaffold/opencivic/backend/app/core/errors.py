"""
OpenCivic — Structured Error Classes

RULE: API error responses NEVER contain stack traces.
Every error has: code (machine-readable), message (human-readable), field (optional).
"""
from typing import Any


class OpenCivicError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An unexpected error occurred.", code: str | None = None, field: str | None = None, detail: Any = None) -> None:
        self.message = message
        self.code = code or self.__class__.code
        self.field = field
        self.detail = detail
        super().__init__(message)


class ValidationError(OpenCivicError):
    status_code = 400; code = "VALIDATION_ERROR"

class InvalidFileFormat(OpenCivicError):
    status_code = 400; code = "INVALID_FILE_FORMAT"

class FileTooLarge(OpenCivicError):
    status_code = 400; code = "FILE_TOO_LARGE"

class InvalidConnectorConfig(OpenCivicError):
    status_code = 400; code = "INVALID_CONNECTOR_CONFIG"

class InvalidWorkflowTransition(OpenCivicError):
    status_code = 400; code = "INVALID_WORKFLOW_TRANSITION"

class SelfApprovalNotAllowed(OpenCivicError):
    status_code = 400; code = "SELF_APPROVAL_NOT_ALLOWED"

class AuthenticationRequired(OpenCivicError):
    status_code = 401; code = "AUTHENTICATION_REQUIRED"

class InvalidToken(OpenCivicError):
    status_code = 401; code = "INVALID_TOKEN"

class InvalidApiKey(OpenCivicError):
    status_code = 401; code = "INVALID_API_KEY"

class PermissionDenied(OpenCivicError):
    status_code = 403; code = "PERMISSION_DENIED"

class TenantSuspended(OpenCivicError):
    status_code = 403; code = "TENANT_SUSPENDED"

class FeatureDisabled(OpenCivicError):
    status_code = 403; code = "FEATURE_DISABLED"

class AiDisabled(OpenCivicError):
    status_code = 403; code = "AI_DISABLED"

class NotFound(OpenCivicError):
    status_code = 404; code = "NOT_FOUND"

class DatasetNotFound(OpenCivicError):
    status_code = 404; code = "DATASET_NOT_FOUND"

class ConnectorNotFound(OpenCivicError):
    status_code = 404; code = "CONNECTOR_NOT_FOUND"

class UserNotFound(OpenCivicError):
    status_code = 404; code = "USER_NOT_FOUND"

class SlugConflict(OpenCivicError):
    status_code = 409; code = "SLUG_CONFLICT"

class DatasetArchived(OpenCivicError):
    status_code = 410; code = "DATASET_ARCHIVED"

class VirusScanFailed(OpenCivicError):
    status_code = 422; code = "VIRUS_SCAN_FAILED"

class SchemaInferenceError(OpenCivicError):
    status_code = 422; code = "SCHEMA_INFERENCE_ERROR"

class RateLimitExceeded(OpenCivicError):
    status_code = 429; code = "RATE_LIMIT_EXCEEDED"

class DatabaseError(OpenCivicError):
    status_code = 500; code = "DATABASE_ERROR"

class StorageError(OpenCivicError):
    status_code = 500; code = "STORAGE_ERROR"

class ConnectorError(OpenCivicError):
    status_code = 500; code = "CONNECTOR_ERROR"

class LlmError(OpenCivicError):
    status_code = 500; code = "LLM_ERROR"

class EncryptionError(OpenCivicError):
    status_code = 500; code = "ENCRYPTION_ERROR"
