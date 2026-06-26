"""User profile endpoints."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.v1.dependencies.auth import AuthRequired
from app.db.models import User
from app.db.session import ReadSession

router = APIRouter()


@router.get("/me")
async def get_current_user_profile(
    session: ReadSession,
    current_user: AuthRequired,
) -> dict:
    """Return the authenticated user's profile from the tenant users table."""
    user = await session.scalar(select(User).where(User.id == current_user.user_id))
    if user is None:
        return {
            "data": {
                "id": str(current_user.user_id),
                "tenant_id": str(current_user.tenant_id),
                "roles": current_user.roles,
                "email": None,
                "name": None,
            },
            "meta": {},
            "errors": [],
        }
    return {
        "data": {
            "id": str(user.id),
            "tenant_id": str(user.tenant_id),
            "email": user.email,
            "name": user.name,
            "roles": list(user.roles),
            "status": user.status,
        },
        "meta": {},
        "errors": [],
    }
