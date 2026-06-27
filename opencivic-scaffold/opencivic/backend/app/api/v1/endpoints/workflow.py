"""Maker-checker workflow endpoints."""
import uuid
from pydantic import BaseModel
from fastapi import APIRouter
from app.api.v1.dependencies.auth import AuthRequired
from app.db.session import WriteSession, ReadSession
router = APIRouter()

class ReviewAction(BaseModel):
    action: str  # approve | reject | request_changes
    notes: str

@router.get("/queue")
async def get_review_queue(session: ReadSession, current_user: AuthRequired):
    return {"data": [], "meta": {}, "errors": []}

@router.post("/{submission_id}/review")
async def review_submission(submission_id: uuid.UUID, action: ReviewAction,
    session: WriteSession, current_user: AuthRequired):
    """RULE: checker_id != maker_id enforced at DB level."""
    return {"data": {"status": action.action}, "meta": {}, "errors": []}
