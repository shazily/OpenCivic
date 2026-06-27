"""SQLAlchemy declarative base for OpenCivic ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata registry for Alembic autogenerate and ORM models."""
