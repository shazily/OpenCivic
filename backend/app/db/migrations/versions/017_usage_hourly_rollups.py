"""017 — usage_hourly_rollups table.

Revision ID: 017
Revises: 016
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_hourly_rollups",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("hour_bucket", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("bytes_total", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "dataset_id",
            "event_type",
            "hour_bucket",
            name="uq_usage_hourly_bucket",
        ),
    )
    op.create_index("ix_usage_hourly_tenant_id", "usage_hourly_rollups", ["tenant_id"])
    op.create_index("ix_usage_hourly_dataset_id", "usage_hourly_rollups", ["dataset_id"])
    op.create_index("ix_usage_hourly_hour_bucket", "usage_hourly_rollups", ["hour_bucket"])

    op.execute("ALTER TABLE usage_hourly_rollups ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE usage_hourly_rollups FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY usage_hourly_rollups_tenant_select ON usage_hourly_rollups
            FOR SELECT USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
        CREATE POLICY usage_hourly_rollups_tenant_insert ON usage_hourly_rollups
            FOR INSERT WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
        CREATE POLICY usage_hourly_rollups_tenant_update ON usage_hourly_rollups
            FOR UPDATE USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON usage_hourly_rollups TO opencivic_app")
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE usage_hourly_rollups_id_seq TO opencivic_app"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS usage_hourly_rollups_tenant_select ON usage_hourly_rollups")
    op.execute("DROP POLICY IF EXISTS usage_hourly_rollups_tenant_insert ON usage_hourly_rollups")
    op.execute("DROP POLICY IF EXISTS usage_hourly_rollups_tenant_update ON usage_hourly_rollups")
    op.drop_index("ix_usage_hourly_hour_bucket", table_name="usage_hourly_rollups")
    op.drop_index("ix_usage_hourly_dataset_id", table_name="usage_hourly_rollups")
    op.drop_index("ix_usage_hourly_tenant_id", table_name="usage_hourly_rollups")
    op.drop_table("usage_hourly_rollups")
