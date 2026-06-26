"""Maker-checker workflow endpoints."""

import uuid
from typing import Literal

from fastapi import APIRouter, Query

from app.api.v1.dependencies.permissions import ApproverRequired, PublisherRequired, StewardRequired
from app.db.session import ReadSession, WriteSession
from app.repositories.event_repository import EventRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.workflow import (
    ApproveActionRequest,
    GovernanceSummary,
    ReviewActionRequest,
    WorkflowSubmissionResponse,
)
from app.services.governance.governance_export_service import (
    build_governance_csv,
    build_governance_pdf_base64,
)
from app.services.governance.workflow_service import WorkflowService

router = APIRouter()


@router.get("/governance/summary")
async def governance_summary(
    session: ReadSession,
    current_user: StewardRequired,
    days: int = Query(30, ge=7, le=90),
) -> dict:
    """Governance queue metrics for the steward console."""
    totals = await WorkflowRepository(session).governance_summary(days=days)
    summary = GovernanceSummary(**totals)
    return {
        "data": summary.model_dump(mode="json"),
        "meta": {"report_days": days},
        "errors": [],
    }


@router.get("/governance/export")
async def governance_export(
    session: ReadSession,
    current_user: StewardRequired,
    days: int = Query(30, ge=7, le=90),
    format: Literal["csv", "pdf"] = Query("csv"),
) -> dict:
    """Export governance summary metrics as CSV or minimal PDF stub."""
    totals = await WorkflowRepository(session).governance_summary(days=days)
    if format == "pdf":
        return {
            "data": {
                "format": "pdf",
                "filename": f"governance-summary-{days}d.pdf",
                "content_base64": build_governance_pdf_base64(totals, days=days),
                "report_days": days,
            },
            "meta": {"report_days": days},
            "errors": [],
        }
    csv_content = build_governance_csv(totals)
    return {
        "data": {
            "format": "csv",
            "filename": f"governance-summary-{days}d.csv",
            "content": csv_content,
            "report_days": days,
        },
        "meta": {"report_days": days},
        "errors": [],
    }


@router.get("/queue/export")
async def export_review_queue(
    session: ReadSession,
    current_user: StewardRequired,
) -> dict:
    """Export pending review submissions as CSV (per-submission stub)."""
    items = await WorkflowRepository(session).list_pending_review()
    lines = [
        "id,dataset_id,maker_id,status,submitted_at,review_due_at,sla_breached,maker_notes",
    ]
    for item in items:
        submitted = item.submitted_at.isoformat() if item.submitted_at else ""
        due = item.review_due_at.isoformat() if item.review_due_at else ""
        notes = (item.maker_notes or "").replace('"', '""')
        lines.append(
            f"{item.id},{item.dataset_id},{item.maker_id},{item.status},"
            f"{submitted},{due},{item.sla_breached},\"{notes}\""
        )
    csv_content = "\n".join(lines) + "\n"
    return {
        "data": {
            "format": "csv",
            "filename": "review-queue.csv",
            "content": csv_content,
            "row_count": len(items),
        },
        "meta": {"total_count": len(items)},
        "errors": [],
    }


@router.get("/queue")
async def get_review_queue(
    session: ReadSession,
    current_user: StewardRequired,
) -> dict:
    """List submissions awaiting steward review."""
    repo = WorkflowRepository(session)
    items = await repo.list_pending_review()
    return {
        "data": [
            WorkflowSubmissionResponse.model_validate(item).model_dump(mode="json")
            for item in items
        ],
        "meta": {"total_count": len(items)},
        "errors": [],
    }


@router.get("/approval-queue")
async def get_approval_queue(
    session: ReadSession,
    current_user: ApproverRequired,
) -> dict:
    """List submissions awaiting senior approval (two-gate workflow)."""
    repo = WorkflowRepository(session)
    items = await repo.list_pending_approval()
    return {
        "data": [
            WorkflowSubmissionResponse.model_validate(item).model_dump(mode="json")
            for item in items
        ],
        "meta": {"total_count": len(items)},
        "errors": [],
    }


@router.get("/publisher/timeline")
async def publisher_workflow_timeline(
    session: ReadSession,
    current_user: PublisherRequired,
    limit: int = 25,
) -> dict:
    """Recent workflow events across the publisher's datasets."""
    events = await EventRepository(session).list_for_publisher(
        current_user.user_id,
        limit=limit,
    )
    return {
        "data": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "dataset_id": str(event.aggregate_id),
                "created_at": event.created_at.isoformat(),
                "payload": event.payload,
            }
            for event in events
        ],
        "meta": {"total_count": len(events)},
        "errors": [],
    }


@router.post("/{submission_id}/review")
async def review_submission(
    submission_id: uuid.UUID,
    body: ReviewActionRequest,
    session: WriteSession,
    current_user: StewardRequired,
) -> dict:
    """Steward approve, reject, or request changes on a submission."""
    service = WorkflowService(session, current_user.tenant_id)
    submission = await service.review(
        submission_id,
        current_user.user_id,
        body.action,
        body.notes,
    )
    return {
        "data": WorkflowSubmissionResponse.model_validate(submission).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.post("/{submission_id}/approve")
async def approve_submission(
    submission_id: uuid.UUID,
    body: ApproveActionRequest,
    session: WriteSession,
    current_user: ApproverRequired,
) -> dict:
    """Senior approver publishes a high-sensitivity submission."""
    service = WorkflowService(session, current_user.tenant_id)
    submission = await service.approve(
        submission_id,
        current_user.user_id,
        body.notes,
    )
    return {
        "data": WorkflowSubmissionResponse.model_validate(submission).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }
