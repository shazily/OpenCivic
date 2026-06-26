"""008 — workflow_submissions table with maker-checker constraints.

Revision ID: 008
Revises: 007
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("maker_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("checker_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approver_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_review"),
        sa.Column("maker_notes", sa.Text(), nullable=True),
        sa.Column("checker_notes", sa.Text(), nullable=True),
        sa.Column("approver_notes", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_breached", sa.Boolean(), nullable=False, server_default="false"),
        sa.CheckConstraint(
            "checker_id IS NULL OR checker_id != maker_id",
            name="workflow_checker_not_maker",
        ),
        sa.CheckConstraint(
            "approver_id IS NULL OR approver_id != maker_id",
            name="workflow_approver_not_maker",
        ),
        sa.CheckConstraint(
            "approver_id IS NULL OR checker_id IS NULL OR approver_id != checker_id",
            name="workflow_approver_not_checker",
        ),
    )
    op.create_index("ix_workflow_submissions_tenant_id", "workflow_submissions", ["tenant_id"])
    op.create_index("ix_workflow_submissions_dataset_id", "workflow_submissions", ["dataset_id"])
    op.create_index("ix_workflow_submissions_status", "workflow_submissions", ["status"])

    op.execute("ALTER TABLE workflow_submissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workflow_submissions FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY workflow_submissions_tenant_select ON workflow_submissions
            FOR SELECT
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );

        CREATE POLICY workflow_submissions_tenant_insert ON workflow_submissions
            FOR INSERT
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );

        CREATE POLICY workflow_submissions_tenant_update ON workflow_submissions
            FOR UPDATE
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_submissions TO opencivic_app"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS workflow_submissions_tenant_select ON workflow_submissions")
    op.execute("DROP POLICY IF EXISTS workflow_submissions_tenant_insert ON workflow_submissions")
    op.execute("DROP POLICY IF EXISTS workflow_submissions_tenant_update ON workflow_submissions")
    op.drop_index("ix_workflow_submissions_status", table_name="workflow_submissions")
    op.drop_index("ix_workflow_submissions_dataset_id", table_name="workflow_submissions")
    op.drop_index("ix_workflow_submissions_tenant_id", table_name="workflow_submissions")
    op.drop_table("workflow_submissions")
