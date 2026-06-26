from functools import lru_cache
from typing import Literal

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    VERSION: str = "0.1.0"
    DEPLOYMENT_MODE: Literal["cloud", "selfhosted", "airgap"] = "selfhosted"
    SECRET_KEY: str
    DOCS_ENABLED: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://opencivic:password@pgbouncer:6432/opencivic"
    DATABASE_MIGRATION_URL: str = ""
    DATABASE_WRITE_URL: str = (
        "postgresql+asyncpg://opencivic:password@postgres-primary:5432/opencivic"
    )
    DATABASE_READ_URL: str = (
        "postgresql+asyncpg://opencivic:password@postgres-replica:5432/opencivic"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    VALKEY_URL: str = "valkey://:password@valkey:6379/0"
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: str = ""
    STORAGE_PROVIDER: Literal["minio", "s3", "azure_blob", "gcs"] = "minio"
    MINIO_ENDPOINT: str = "http://minio:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "opencivic"
    KEYCLOAK_URL: str = "http://keycloak:8080"
    KEYCLOAK_REALM: str = "dev"
    KEYCLOAK_CLIENT_ID: str = "opencivic-portal"
    KEYCLOAK_ENABLED: bool = False
    KEYCLOAK_ADMIN_CLIENT_ID: str = "opencivic-admin"
    KEYCLOAK_ADMIN_CLIENT_SECRET: str = ""
    LLM_PROVIDER: Literal["openai", "anthropic", "gemini", "ollama", "openai_compatible"] = "ollama"
    LLM_MODEL: str = "llama3.2"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "http://ollama:11434"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.1
    LLM_CONFIDENCE_THRESHOLD: float = 0.7
    AI_MODE: Literal["assist", "automate", "disabled"] = "assist"
    AI_SANDBOX_TIMEOUT_SECONDS: int = 10
    AI_MAX_CELL_LENGTH: int = 2000
    CLAMAV_HOST: str = "clamav"
    CLAMAV_PORT: int = 3310
    CLAMAV_ENABLED: bool = True
    CLAMAV_TIMEOUT_SECONDS: int = 30
    UPLOAD_MAX_BYTES: int = 52_428_800
    ALLOWED_UPLOAD_EXTENSIONS: str = "csv,tsv,json,jsonl,xls,xlsx,parquet,pdf"
    DEFAULT_API_RATE_LIMIT_PER_MIN: int = 1000
    CORS_ORIGINS: str = "http://localhost:3000"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@opencivic.local"
    SMTP_TLS: bool = True
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector:4317"
    OTEL_SERVICE_NAME: str = "opencivic-api"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    WORKFLOW_REVIEW_SLA_HOURS: int = 48
    STALENESS_CHECK_INTERVAL_MINUTES: int = 1
    CONNECTOR_CIRCUIT_BREAKER_THRESHOLD: int = 5
    CONNECTOR_CIRCUIT_BREAKER_TIMEOUT_SECONDS: int = 300
    DEV_AUTH_ENABLED: bool = False
    DEV_AUTH_TOKEN: str = "dev-local-token-change-me"  # noqa: S105
    DEV_TENANT_ID: str = "00000000-0000-0000-0000-000000000001"
    DEV_USER_ID: str = "00000000-0000-0000-0000-000000000002"
    DEV_LICENCE_ID: str = "00000000-0000-0000-0000-000000000003"
    DEV_STEWARD_USER_ID: str = "00000000-0000-0000-0000-000000000010"
    DEV_STEWARD_AUTH_TOKEN: str = "dev-steward-token-change-me"  # noqa: S105
    DEV_ADMIN_USER_ID: str = "00000000-0000-0000-0000-000000000011"
    DEV_ADMIN_AUTH_TOKEN: str = "dev-admin-token-change-me"  # noqa: S105
    DEV_DEVELOPER_USER_ID: str = "00000000-0000-0000-0000-000000000012"
    DEV_DEVELOPER_AUTH_TOKEN: str = "dev-developer-token-change-me"  # noqa: S105
    REFRESH_COOKIE_NAME: str = "opencivic_refresh"
    REFRESH_COOKIE_MAX_AGE_SECONDS: int = 604_800
    KEYCLOAK_CLIENT_SECRET: str = ""
    TUS_ENABLED: bool = False
    TUS_URL: str = "http://127.0.0.1:1080/files/"
    TUS_INTERNAL_URL: str = "http://tusd:1080/files/"
    TUS_HOOK_SECRET: str = ""
    SCIM_WEBHOOK_SECRET: str = ""
    EDGE_RATE_LIMIT_ENABLED: bool = True
    GATEWAY_RATE_LIMIT_ENABLED: bool = True
    MFA_ENFORCEMENT_ENABLED: bool = False
    PGBACKREST_ENABLED: bool = False
    PGBACKREST_STANZA: str = "opencivic"
    PGBACKREST_COMMAND: str = "pgbackrest"
    BACKUP_VERIFY_HOOK_SECRET: str = ""
    EDGE_AUTH_ENABLED: bool = False
    GATEWAY_AUTH_SECRET: str = ""
    FLOWER_URL: str = ""
    FLOWER_USER: str = ""
    FLOWER_PASSWORD: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_migration_url(self) -> str:
        """Migration/superuser URL for operations that must bypass tenant RLS."""
        if self.DATABASE_MIGRATION_URL:
            return self.DATABASE_MIGRATION_URL
        return self.DATABASE_WRITE_URL

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        """Parsed CORS allowlist from comma-separated CORS_ORIGINS env value."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def derive_celery(self):
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.VALKEY_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.VALKEY_URL
        return self

    @property
    def is_airgapped(self):
        return self.DEPLOYMENT_MODE == "airgap"

    @property
    def ai_enabled(self):
        return self.AI_MODE != "disabled"

    @property
    def allowed_upload_extensions(self) -> list[str]:
        """Parsed upload extension allowlist."""
        return [
            extension.strip().lower()
            for extension in self.ALLOWED_UPLOAD_EXTENSIONS.split(",")
            if extension.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
