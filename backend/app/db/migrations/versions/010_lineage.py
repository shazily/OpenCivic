"""010 — lineage graph tables.

Revision ID: 010
Revises: 009
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lineage_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "lineage_edges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "from_node_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lineage_nodes.id"),
            nullable=False,
        ),
        sa.Column(
            "to_node_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lineage_nodes.id"),
            nullable=False,
        ),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lineage_nodes_tenant_id", "lineage_nodes", ["tenant_id"])
    op.create_index("ix_lineage_edges_tenant_id", "lineage_edges", ["tenant_id"])
    op.execute("ALTER TABLE lineage_nodes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lineage_edges ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lineage_nodes FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lineage_edges FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY lineage_nodes_tenant ON lineage_nodes
            FOR ALL USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
        CREATE POLICY lineage_edges_tenant ON lineage_edges
            FOR ALL USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON lineage_nodes TO opencivic_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON lineage_edges TO opencivic_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS lineage_nodes_tenant ON lineage_nodes")
    op.execute("DROP POLICY IF EXISTS lineage_edges_tenant ON lineage_edges")
    op.drop_index("ix_lineage_edges_tenant_id", table_name="lineage_edges")
    op.drop_index("ix_lineage_nodes_tenant_id", table_name="lineage_nodes")
    op.drop_table("lineage_edges")
    op.drop_table("lineage_nodes")
