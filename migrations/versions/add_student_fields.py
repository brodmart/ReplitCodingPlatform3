"""add missing student fields

Revision ID: add_student_fields
Revises: 002_add_password_reset_fields
Create Date: 2025-01-20 17:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_student_fields'
down_revision = '002_add_password_reset_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to student table
    op.add_column('student', sa.Column('avatar_path', sa.String(256), nullable=True))
    op.add_column('student', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('student', sa.Column('last_failed_login', sa.DateTime(), nullable=True))
    op.add_column('student', sa.Column('account_locked_until', sa.DateTime(), nullable=True))
    op.add_column('student', sa.Column('reset_password_token', sa.String(100), nullable=True, unique=True))
    op.add_column('student', sa.Column('reset_password_token_expiration', sa.DateTime(), nullable=True))
    op.add_column('student', sa.Column('score', sa.Integer(), nullable=False, server_default='0'))
    
    # Add index for username lookups
    op.create_index('idx_student_username', 'student', ['username'])


def downgrade():
    # Remove columns in reverse order
    op.drop_index('idx_student_username')
    op.drop_column('student', 'score')
    op.drop_column('student', 'reset_password_token_expiration')
    op.drop_column('student', 'reset_password_token')
    op.drop_column('student', 'account_locked_until')
    op.drop_column('student', 'last_failed_login')
    op.drop_column('student', 'failed_login_attempts')
    op.drop_column('student', 'avatar_path')
