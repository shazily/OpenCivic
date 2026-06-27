"""014 — webhooks table for developer console.

Revision ID: 014
Revises: 013
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("secret", sa.LargeBinary(), nullable=False),
        sa.Column("events", ARRAY(sa.Text()), nullable=False),
        sa.Column("dataset_id", UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_webhooks_tenant_id", "webhooks", ["tenant_id"])
    op.execute("ALTER TABLE webhooks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE webhooks FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY webhooks_tenant_select ON webhooks
            FOR SELECT USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
        CREATE POLICY webhooks_tenant_insert ON webhooks
            FOR INSERT WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
        CREATE POLICY webhooks_tenant_update ON webhooks
            FOR UPDATE USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON webhooks TO opencivic_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS webhooks_tenant_select ON webhooks")
    op.execute("DROP POLICY IF EXISTS webhooks_tenant_insert ON webhooks")
    op.execute("DROP POLICY IF EXISTS webhooks_tenant_update ON webhooks")
    op.drop_index("ix_webhooks_tenant_id", table_name="webhooks")
    op.drop_table("webhooks")
