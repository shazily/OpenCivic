"""015 — feedback and usage_events tables.

Revision ID: 015
Revises: 014
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("resolved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="ck_feedback_rating"),
    )
    op.create_index("ix_feedback_tenant_id", "feedback", ["tenant_id"])
    op.create_index("ix_feedback_dataset_id", "feedback", ["dataset_id"])

    op.create_table(
        "usage_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("api_key_id", UUID(as_uuid=True), sa.ForeignKey("api_keys.id"), nullable=True),
        sa.Column("format", sa.String(20), nullable=True),
        sa.Column("bytes", sa.BigInteger(), nullable=True),
        sa.Column("response_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_usage_events_tenant_id", "usage_events", ["tenant_id"])
    op.create_index("ix_usage_events_dataset_id", "usage_events", ["dataset_id"])
    op.create_index("ix_usage_events_event_type", "usage_events", ["event_type"])

    for table in ("feedback", "usage_events"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_select ON {table}
                FOR SELECT USING (
                    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                );
            CREATE POLICY {table}_tenant_insert ON {table}
                FOR INSERT WITH CHECK (
                    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                );
            CREATE POLICY {table}_tenant_update ON {table}
                FOR UPDATE USING (
                    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                );
        """)
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO opencivic_app")

    op.execute("GRANT USAGE, SELECT ON SEQUENCE usage_events_id_seq TO opencivic_app")


def downgrade() -> None:
    for table in ("usage_events", "feedback"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_update ON {table}")
    op.drop_index("ix_usage_events_event_type", table_name="usage_events")
    op.drop_index("ix_usage_events_dataset_id", table_name="usage_events")
    op.drop_index("ix_usage_events_tenant_id", table_name="usage_events")
    op.drop_table("usage_events")
    op.drop_index("ix_feedback_dataset_id", table_name="feedback")
    op.drop_index("ix_feedback_tenant_id", table_name="feedback")
    op.drop_table("feedback")
