from functools import lru_cache
from typing import Literal
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    VERSION: str = "0.1.0"
    DEPLOYMENT_MODE: Literal["cloud","selfhosted","airgap"] = "selfhosted"
    SECRET_KEY: str
    DOCS_ENABLED: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://opencivic:password@pgbouncer:6432/opencivic"
    DATABASE_WRITE_URL: str = "postgresql+asyncpg://opencivic:password@postgres-primary:5432/opencivic"
    DATABASE_READ_URL: str = "postgresql+asyncpg://opencivic:password@postgres-replica:5432/opencivic"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    VALKEY_URL: str = "valkey://:password@valkey:6379/0"
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: str = ""
    STORAGE_PROVIDER: Literal["minio","s3","azure_blob","gcs"] = "minio"
    MINIO_ENDPOINT: str = "http://minio:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "opencivic"
    KEYCLOAK_URL: str = "http://keycloak:8080"
    KEYCLOAK_ADMIN_CLIENT_ID: str = "opencivic-admin"
    KEYCLOAK_ADMIN_CLIENT_SECRET: str = ""
    LLM_PROVIDER: Literal["openai","anthropic","gemini","ollama","openai_compatible"] = "ollama"
    LLM_MODEL: str = "llama3.2"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "http://ollama:11434"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.1
    LLM_CONFIDENCE_THRESHOLD: float = 0.7
    AI_MODE: Literal["assist","automate","disabled"] = "assist"
    AI_SANDBOX_TIMEOUT_SECONDS: int = 10
    AI_MAX_CELL_LENGTH: int = 2000
    CLAMAV_HOST: str = "clamav"
    CLAMAV_PORT: int = 3310
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@opencivic.local"
    SMTP_TLS: bool = True
    LOG_LEVEL: Literal["DEBUG","INFO","WARNING","ERROR"] = "INFO"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector:4317"
    OTEL_SERVICE_NAME: str = "opencivic-api"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    WORKFLOW_REVIEW_SLA_HOURS: int = 48
    STALENESS_CHECK_INTERVAL_MINUTES: int = 1
    CONNECTOR_CIRCUIT_BREAKER_THRESHOLD: int = 5
    CONNECTOR_CIRCUIT_BREAKER_TIMEOUT_SECONDS: int = 300

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        return [o.strip() for o in v.split(",")] if isinstance(v, str) else v

    @model_validator(mode="after")
    def derive_celery(self):
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.VALKEY_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.VALKEY_URL
        return self

    @property
    def is_airgapped(self): return self.DEPLOYMENT_MODE == "airgap"
    @property
    def ai_enabled(self): return self.AI_MODE != "disabled"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
