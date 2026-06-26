"""001 — Platform schema: tenants, audit_log, plans, super_admins.
Revision ID: 001
Revises: —
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS platform")
    op.create_table("tenants", 
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(63), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("schema_name", sa.String(63), nullable=True),
        sa.Column("db_dsn", sa.LargeBinary, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("feature_flags", JSONB, nullable=False, server_default="{}"),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="platform",
    )
    op.create_table("audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="platform",
    )
    # INSERT-ONLY trigger — no UPDATE or DELETE ever
    op.execute("""
        CREATE OR REPLACE FUNCTION platform.prevent_audit_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit log is immutable — UPDATE and DELETE are not permitted';
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER audit_log_immutable
        BEFORE UPDATE OR DELETE ON platform.audit_log
        FOR EACH ROW EXECUTE FUNCTION platform.prevent_audit_modification();
    """)

def downgrade():
    op.drop_table("audit_log", schema="platform")
    op.drop_table("tenants", schema="platform")
    op.execute("DROP SCHEMA IF EXISTS platform CASCADE")
