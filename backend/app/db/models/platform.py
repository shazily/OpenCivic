"""Platform schema ORM models — cross-tenant metadata."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class Tenant(Base):
    """Registered organisation on the platform."""

    __tablename__ = "tenants"
    __table_args__ = {"schema": "platform"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    schema_name: Mapped[str | None] = mapped_column(String(63), nullable=True)
    db_dsn: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    feature_flags: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Plan(Base):
    """Subscription plan limits for tenants."""

    __tablename__ = "plans"
    __table_args__ = {"schema": "platform"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    max_datasets: Mapped[int | None] = mapped_column(nullable=True)
    max_users: Mapped[int | None] = mapped_column(nullable=True)
    max_storage_gb: Mapped[int | None] = mapped_column(nullable=True)
    api_rate_limit_per_min: Mapped[int | None] = mapped_column(nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    connectors_enabled: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    price_monthly: Mapped[float | None] = mapped_column(nullable=True)


class SuperAdmin(Base):
    """Platform super administrator account."""

    __tablename__ = "super_admins"
    __table_args__ = {"schema": "platform"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    keycloak_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
