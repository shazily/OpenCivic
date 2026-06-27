"""004 — Sprint 1: platform plans/super_admins, tenant_id columns, tenant RLS.

Revision ID: 004
Revises: 003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

TENANT_TABLES = ("users", "licences", "datasets", "events")


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("max_datasets", sa.Integer(), nullable=True),
        sa.Column("max_users", sa.Integer(), nullable=True),
        sa.Column("max_storage_gb", sa.Integer(), nullable=True),
        sa.Column("api_rate_limit_per_min", sa.Integer(), nullable=True),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("connectors_enabled", JSONB, nullable=True),
        sa.Column("price_monthly", sa.Numeric(10, 2), nullable=True),
        schema="platform",
    )
    op.create_table(
        "super_admins",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("keycloak_user_id", sa.String(255), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        schema="platform",
    )

    for table in TENANT_TABLES:
        op.add_column(
            table,
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        )

    op.drop_constraint("datasets_slug_key", "datasets", type_="unique")
    op.create_index("ix_datasets_tenant_slug", "datasets", ["tenant_id", "slug"], unique=True)

    for table in TENANT_TABLES:
        op.alter_column(table, "tenant_id", nullable=False)
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])

    op.execute("DROP POLICY IF EXISTS datasets_public_read ON datasets")
    op.execute("DROP POLICY IF EXISTS datasets_write ON datasets")
    op.execute("DROP POLICY IF EXISTS users_self_read ON users")

    op.execute("""
        CREATE POLICY datasets_tenant_select ON datasets
            FOR SELECT
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                OR (access_level = 'public' AND status = 'published')
            );

        CREATE POLICY datasets_tenant_insert ON datasets
            FOR INSERT
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );

        CREATE POLICY datasets_tenant_update ON datasets
            FOR UPDATE
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );

        CREATE POLICY datasets_tenant_delete ON datasets
            FOR DELETE
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)

    op.execute("""
        CREATE POLICY users_tenant_select ON users
            FOR SELECT
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );

        CREATE POLICY users_tenant_insert ON users
            FOR INSERT
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)

    op.execute("""
        CREATE POLICY events_tenant_select ON events
            FOR SELECT
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );

        CREATE POLICY events_tenant_insert ON events
            FOR INSERT
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)

    op.execute("""
        CREATE POLICY licences_tenant_select ON licences
            FOR SELECT
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );

        CREATE POLICY licences_tenant_insert ON licences
            FOR INSERT
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS datasets_tenant_select ON datasets")
    op.execute("DROP POLICY IF EXISTS datasets_tenant_insert ON datasets")
    op.execute("DROP POLICY IF EXISTS datasets_tenant_update ON datasets")
    op.execute("DROP POLICY IF EXISTS datasets_tenant_delete ON datasets")
    op.execute("DROP POLICY IF EXISTS users_tenant_select ON users")
    op.execute("DROP POLICY IF EXISTS users_tenant_insert ON users")
    op.execute("DROP POLICY IF EXISTS events_tenant_select ON events")
    op.execute("DROP POLICY IF EXISTS events_tenant_insert ON events")
    op.execute("DROP POLICY IF EXISTS licences_tenant_select ON licences")
    op.execute("DROP POLICY IF EXISTS licences_tenant_insert ON licences")

    op.drop_index("ix_datasets_tenant_slug", table_name="datasets")
    op.create_unique_constraint("datasets_slug_key", "datasets", ["slug"])

    for table in reversed(TENANT_TABLES):
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")

    op.drop_table("super_admins", schema="platform")
    op.drop_table("plans", schema="platform")
