"""add soft delete and audit functionality

Revision ID: add_soft_delete_and_audit
Create Date: 2025-01-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('changes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['student.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Add soft delete column to coding_activity
    op.add_column('coding_activity', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('coding_activity', sa.Column('version', sa.Integer(), nullable=True))
    
    # Create index for soft delete queries
    op.create_index('idx_coding_activity_deleted_at', 'coding_activity', ['deleted_at'])

def downgrade():
    op.drop_index('idx_coding_activity_deleted_at', 'coding_activity')
    op.drop_column('coding_activity', 'version')
    op.drop_column('coding_activity', 'deleted_at')
    op.drop_table('audit_log')
