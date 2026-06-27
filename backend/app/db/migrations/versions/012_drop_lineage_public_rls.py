"""012 — Drop recursive lineage public RLS policies (lineage via tenant context only).

Revision ID: 012
Revises: 011
"""

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS lineage_edges_public_read ON lineage_edges")
    op.execute("DROP POLICY IF EXISTS lineage_nodes_public_read ON lineage_nodes")


def downgrade() -> None:
    op.execute("""
        CREATE POLICY lineage_nodes_public_read ON lineage_nodes
            FOR SELECT
            USING (
                (
                    type = 'dataset'
                    AND (metadata->>'dataset_id') IS NOT NULL
                    AND EXISTS (
                        SELECT 1 FROM datasets d
                        WHERE d.id = (metadata->>'dataset_id')::uuid
                          AND d.access_level = 'public'
                          AND d.status = 'published'
                    )
                )
                OR EXISTS (
                    SELECT 1 FROM lineage_edges e
                    JOIN lineage_nodes dn
                      ON dn.id IN (e.from_node_id, e.to_node_id)
                     AND dn.type = 'dataset'
                    JOIN datasets d ON d.id = (dn.metadata->>'dataset_id')::uuid
                    WHERE (e.from_node_id = lineage_nodes.id OR e.to_node_id = lineage_nodes.id)
                      AND d.access_level = 'public'
                      AND d.status = 'published'
                )
            );

        CREATE POLICY lineage_edges_public_read ON lineage_edges
            FOR SELECT
            USING (
                EXISTS (
                    SELECT 1 FROM lineage_nodes dn
                    JOIN datasets d ON d.id = (dn.metadata->>'dataset_id')::uuid
                    WHERE dn.type = 'dataset'
                      AND (dn.id = lineage_edges.from_node_id OR dn.id = lineage_edges.to_node_id)
                      AND d.access_level = 'public'
                      AND d.status = 'published'
                )
            );
    """)
