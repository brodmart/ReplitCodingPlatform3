"""reset non admin users

Revision ID: reset_non_admin_users
Revises: add_student_fields
Create Date: 2025-01-20 17:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'reset_non_admin_users'
down_revision = 'add_student_fields'
branch_labels = None
depends_on = None

def upgrade():
    # Clear non-admin user data
    op.execute("""
        DELETE FROM student
        WHERE is_admin IS NOT TRUE OR is_admin IS NULL;
    """)

    # Reset sequence if needed
    op.execute("""
        SELECT setval('student_id_seq', 
            CASE 
                WHEN EXISTS (SELECT 1 FROM student) 
                THEN (SELECT MAX(id) FROM student)
                ELSE 1
            END);
    """)

def downgrade():
    # Cannot restore deleted data
    pass