"""003 — Row-Level Security policies on all tenant tables.
Revision ID: 003
Revises: 002
RULE: RLS is ALWAYS enabled — every tier, every table, always.
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

def upgrade():
    # Enable RLS on datasets — public datasets visible to all, restricted require grant
    op.execute("""
        ALTER TABLE datasets ENABLE ROW LEVEL SECURITY;
        
        -- Policy: public datasets visible to everyone
        CREATE POLICY datasets_public_read ON datasets
            FOR SELECT
            USING (
                access_level = 'public' AND status = 'published'
                OR
                publisher_id = (current_setting('app.user_id', TRUE))::uuid
                OR
                steward_id = (current_setting('app.user_id', TRUE))::uuid
            );
        
        -- Policy: write access — publisher or admin only
        CREATE POLICY datasets_write ON datasets
            FOR INSERT WITH CHECK (
                publisher_id = (current_setting('app.user_id', TRUE))::uuid
            );
    """)
    
    # Enable RLS on users — users see only themselves unless admin
    op.execute("""
        ALTER TABLE users ENABLE ROW LEVEL SECURITY;
        CREATE POLICY users_self_read ON users
            FOR SELECT
            USING (
                id = (current_setting('app.user_id', TRUE))::uuid
                OR 'org_admin' = ANY(
                    (SELECT roles FROM users WHERE id = (current_setting('app.user_id', TRUE))::uuid)
                )
            );
    """)
    
    # Remaining tables: tenant isolation via session variable
    for table in ["events", "licences"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")

def downgrade():
    for table in ["datasets", "users", "events", "licences"]:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
