"""006 — Application DB role subject to RLS (non-superuser, NOBYPASSRLS).

Revision ID: 006
Revises: 005
"""

import os

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def _app_role_password() -> str:
    return os.environ.get(
        "OPENCIVIC_APP_PASSWORD",
        os.environ.get("POSTGRES_PASSWORD", "password"),
    ).replace("'", "''")


def upgrade() -> None:
    password = _app_role_password()
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'opencivic_app') THEN
                CREATE ROLE opencivic_app LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}';
            END IF;
        END
        $$;
        """
    )
    op.execute(f"ALTER ROLE opencivic_app WITH LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
    op.execute("GRANT USAGE ON SCHEMA public, platform TO opencivic_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO opencivic_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA platform TO opencivic_app"
    )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO opencivic_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA platform TO opencivic_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO opencivic_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA platform "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO opencivic_app"
    )


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM opencivic_app")
    op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA platform FROM opencivic_app")
    op.execute("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM opencivic_app")
    op.execute("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA platform FROM opencivic_app")
    op.execute("REVOKE USAGE ON SCHEMA public, platform FROM opencivic_app")
    op.execute("DROP ROLE IF EXISTS opencivic_app")
