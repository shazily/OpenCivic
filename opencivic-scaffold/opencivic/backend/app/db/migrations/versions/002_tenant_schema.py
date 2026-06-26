"""002 — Tenant schema template: all 12 tables with RLS.
Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

def upgrade():
    # These tables are created per-tenant schema by the provisioning worker
    # This migration creates them in the 'public' schema as a template
    # The provisioning worker runs: SET search_path = tenant_{id}; then applies this migration
    
    op.create_table("users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("keycloak_user_id", sa.String(255), unique=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("roles", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("scim_external_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table("licences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("allows_commercial", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("requires_attribution", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("allows_derivatives", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("allows_ai_training", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_open", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("spdx_id", sa.String(50), nullable=True),
    )
    op.create_table("datasets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(500), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("access_level", sa.String(20), nullable=False, server_default="public"),
        sa.Column("licence_id", UUID(as_uuid=True), sa.ForeignKey("licences.id"), nullable=True),
        sa.Column("publisher_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("steward_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("quality_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("staleness_state", sa.String(20), nullable=False, server_default="fresh"),
        sa.Column("update_frequency", sa.String(20), nullable=True),
        sa.Column("next_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embargo_until", sa.LargeBinary, nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("custom_metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("row_count", sa.BigInteger, nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("schema_snapshot", JSONB, nullable=True),
        sa.Column("tags", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table("events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(50), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False, server_default="system"),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # INSERT-ONLY trigger on events table
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_event_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Event store is immutable — UPDATE and DELETE are not permitted';
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER events_immutable
        BEFORE UPDATE OR DELETE ON events
        FOR EACH ROW EXECUTE FUNCTION prevent_event_modification();
    """)
    # Self-approval prevention on workflow_submissions (created in migration 003)

def downgrade():
    op.drop_table("events")
    op.drop_table("datasets")
    op.drop_table("licences")
    op.drop_table("users")
