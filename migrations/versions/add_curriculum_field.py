"""Add curriculum field to coding_activity

Revision ID: add_curriculum_field
Revises: remove_email_field
Create Date: 2025-01-20 18:08:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_curriculum_field'
down_revision = 'remove_email_field'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('coding_activity', sa.Column('curriculum', sa.String(20), nullable=True))
    op.execute("UPDATE coding_activity SET curriculum = 'ICS3U' WHERE curriculum IS NULL")
    op.alter_column('coding_activity', 'curriculum', nullable=False)

def downgrade():
    op.drop_column('coding_activity', 'curriculum')
