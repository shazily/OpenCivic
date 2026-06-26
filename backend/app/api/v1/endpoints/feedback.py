"""Feedback API — public submit, publisher/steward list."""

import uuid

from fastapi import APIRouter, Query, status

from app.api.v1.dependencies.auth import AuthOptional, AuthRequired
from app.api.v1.dependencies.permissions import StewardRequired
from app.core.errors import PermissionDenied, ValidationError
from app.db.session import OptionalWriteSession, ReadSession, WriteSession, set_tenant_context
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.feedback import FeedbackCreateRequest, FeedbackResponse

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: FeedbackCreateRequest,
    session: OptionalWriteSession,
    current_user: AuthOptional,
) -> dict:
    """Submit feedback on a published dataset (anonymous allowed)."""
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(body.dataset_id)
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)

    author_id = current_user.user_id if current_user else None
    feedback = await FeedbackRepository(session).create(
        tenant_id=dataset.tenant_id,
        dataset_id=body.dataset_id,
        feedback_type=body.type,
        author_id=author_id,
        rating=body.rating,
        content=body.content,
    )
    return {
        "data": FeedbackResponse.model_validate(feedback).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.get("/")
async def list_feedback(
    session: ReadSession,
    current_user: AuthRequired,
    dataset_id: uuid.UUID = Query(...),
) -> dict:
    """List feedback for a dataset (publisher or steward)."""
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if (
        dataset.publisher_id != current_user.user_id
        and "data_steward" not in current_user.roles
        and "org_admin" not in current_user.roles
    ):
        raise PermissionDenied(message="You cannot view feedback for this dataset.")

    items = await FeedbackRepository(session).list_for_dataset(dataset_id)
    return {
        "data": [
            FeedbackResponse.model_validate(item).model_dump(mode="json") for item in items
        ],
        "meta": {"total_count": len(items)},
        "errors": [],
    }


@router.patch("/{feedback_id}/resolve")
async def resolve_feedback(
    feedback_id: uuid.UUID,
    session: WriteSession,
    current_user: StewardRequired,
) -> dict:
    """Mark feedback as acknowledged (steward action)."""
    from sqlalchemy import select, update

    from app.db.models import Feedback

    item = await session.scalar(select(Feedback).where(Feedback.id == feedback_id))
    if item is None:
        raise ValidationError(message="Feedback not found.", field="id")

    await session.execute(
        update(Feedback)
        .where(Feedback.id == feedback_id)
        .values(status="acknowledged", resolved_by=current_user.user_id)
    )
    await session.refresh(item)
    return {
        "data": FeedbackResponse.model_validate(item).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }
