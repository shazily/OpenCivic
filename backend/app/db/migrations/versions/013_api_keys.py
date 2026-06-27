"""013 — api_keys table for developer console.

Revision ID: 013
Revises: 012
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("scopes", ARRAY(sa.Text()), nullable=False, server_default="{read}"),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rate_limit_override", sa.Integer(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_owner_id", "api_keys", ["owner_id"])
    op.execute("ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE api_keys FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY api_keys_tenant_select ON api_keys
            FOR SELECT USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
        CREATE POLICY api_keys_tenant_insert ON api_keys
            FOR INSERT WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
        CREATE POLICY api_keys_tenant_update ON api_keys
            FOR UPDATE USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON api_keys TO opencivic_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS api_keys_tenant_select ON api_keys")
    op.execute("DROP POLICY IF EXISTS api_keys_tenant_insert ON api_keys")
    op.execute("DROP POLICY IF EXISTS api_keys_tenant_update ON api_keys")
    op.drop_index("ix_api_keys_owner_id", table_name="api_keys")
    op.drop_index("ix_api_keys_tenant_id", table_name="api_keys")
    op.drop_table("api_keys")
