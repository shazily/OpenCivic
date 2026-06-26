"""009 — connectors table with circuit breaker fields.

Revision ID: 009
Revises: 008
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connectors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("config", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_frequency", sa.String(20), nullable=True),
        sa.Column("circuit_state", sa.String(20), nullable=False, server_default="closed"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("dataset_id", UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_connectors_tenant_id", "connectors", ["tenant_id"])
    op.create_index("ix_connectors_next_sync_at", "connectors", ["next_sync_at"])
    op.execute("ALTER TABLE connectors ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE connectors FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY connectors_tenant_select ON connectors
            FOR SELECT USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
        CREATE POLICY connectors_tenant_insert ON connectors
            FOR INSERT WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
        CREATE POLICY connectors_tenant_update ON connectors
            FOR UPDATE USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON connectors TO opencivic_app")

    op.add_column(
        "datasets",
        sa.Column("workflow_variant", sa.String(30), nullable=False, server_default="standard"),
    )


def downgrade() -> None:
    op.drop_column("datasets", "workflow_variant")
    op.execute("DROP POLICY IF EXISTS connectors_tenant_select ON connectors")
    op.execute("DROP POLICY IF EXISTS connectors_tenant_insert ON connectors")
    op.execute("DROP POLICY IF EXISTS connectors_tenant_update ON connectors")
    op.drop_index("ix_connectors_next_sync_at", table_name="connectors")
    op.drop_index("ix_connectors_tenant_id", table_name="connectors")
    op.drop_table("connectors")
