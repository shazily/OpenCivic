"""018 — users tenant UPDATE RLS policy for SCIM deprovision and admin ops.

Revision ID: 018
Revises: 017
"""

from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE POLICY users_tenant_update ON users
            FOR UPDATE
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS users_tenant_update ON users")
