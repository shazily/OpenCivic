"""011 — Public read RLS for published dataset versions.

Revision ID: 011
Revises: 010
"""

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE POLICY dataset_versions_public_read ON dataset_versions
            FOR SELECT
            USING (
                EXISTS (
                    SELECT 1 FROM datasets d
                    WHERE d.id = dataset_versions.dataset_id
                      AND d.access_level = 'public'
                      AND d.status = 'published'
                )
            );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS dataset_versions_public_read ON dataset_versions")
