"""007 — dataset_versions table with tenant RLS.

Revision ID: 007
Revises: 006
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dataset_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("schema_snapshot", JSONB, nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("raw_file_path", sa.Text(), nullable=True),
        sa.Column("quality_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "dataset_id",
            "version_number",
            name="uq_dataset_versions_dataset_version",
        ),
    )
    op.create_index("ix_dataset_versions_tenant_id", "dataset_versions", ["tenant_id"])
    op.create_index("ix_dataset_versions_dataset_id", "dataset_versions", ["dataset_id"])

    op.execute("ALTER TABLE dataset_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE dataset_versions FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY dataset_versions_tenant_select ON dataset_versions
            FOR SELECT
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );

        CREATE POLICY dataset_versions_tenant_insert ON dataset_versions
            FOR INSERT
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );

        CREATE POLICY dataset_versions_tenant_update ON dataset_versions
            FOR UPDATE
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON dataset_versions TO opencivic_app"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS dataset_versions_tenant_select ON dataset_versions")
    op.execute("DROP POLICY IF EXISTS dataset_versions_tenant_insert ON dataset_versions")
    op.execute("DROP POLICY IF EXISTS dataset_versions_tenant_update ON dataset_versions")
    op.drop_index("ix_dataset_versions_dataset_id", table_name="dataset_versions")
    op.drop_index("ix_dataset_versions_tenant_id", table_name="dataset_versions")
    op.drop_table("dataset_versions")
