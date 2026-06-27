"""Platform tenant API schemas."""

from pydantic import BaseModel, Field


class TenantCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=63)
    display_name: str = Field(min_length=1, max_length=255)
    tier: str = Field(default="standard", pattern="^(standard|professional|enterprise)$")


class TenantResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    tier: str
    status: str
