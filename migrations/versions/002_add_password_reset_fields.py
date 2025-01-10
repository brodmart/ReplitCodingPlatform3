"""add password reset fields

Revision ID: 002_add_password_reset_fields
Revises: 001_simplify_auth
Create Date: 2025-01-10 16:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_add_password_reset_fields'
down_revision = '001_simplify_auth'
branch_labels = None
depends_on = None

def upgrade():
    # Add password reset fields to student table
    op.add_column('student', sa.Column('reset_password_token', sa.String(100), unique=True, nullable=True))
    op.add_column('student', sa.Column('reset_password_token_expiration', sa.DateTime(), nullable=True))
    op.create_unique_constraint('uq_student_reset_password_token', 'student', ['reset_password_token'])

def downgrade():
    # Remove password reset fields from student table
    op.drop_constraint('uq_student_reset_password_token', 'student', type_='unique')
    op.drop_column('student', 'reset_password_token_expiration')
    op.drop_column('student', 'reset_password_token')
