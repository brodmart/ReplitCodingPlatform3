"""remove email field

Revision ID: remove_email_field
Revises: add_student_fields
Create Date: 2025-01-20 18:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'remove_email_field'
down_revision = 'add_student_fields'
branch_labels = None
depends_on = None

def upgrade():
    # Drop email column
    op.drop_column('student', 'email')

def downgrade():
    # Add email column back if needed
    op.add_column('student', sa.Column('email', sa.String(120), nullable=True))
