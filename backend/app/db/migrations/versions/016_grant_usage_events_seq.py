"""016 — grant usage_events sequence to app role.

Revision ID: 016
Revises: 015
"""
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT USAGE, SELECT ON SEQUENCE usage_events_id_seq TO opencivic_app")


def downgrade() -> None:
    op.execute("REVOKE USAGE, SELECT ON SEQUENCE usage_events_id_seq FROM opencivic_app")
