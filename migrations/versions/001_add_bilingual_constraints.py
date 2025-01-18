"""Add bilingual constraints and set NOT NULL

Revision ID: 001_add_bilingual_constraints
Revises: 
Create Date: 2025-01-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers
revision = '001_add_bilingual_constraints'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Set NOT NULL and defaults for courses table
    with op.batch_alter_table('courses') as batch_op:
        # First set default values for existing records
        op.execute("UPDATE courses SET description_en = '' WHERE description_en IS NULL")
        op.execute("UPDATE courses SET description_fr = '' WHERE description_fr IS NULL")
        op.execute("UPDATE courses SET prerequisite_en = '' WHERE prerequisite_en IS NULL")
        op.execute("UPDATE courses SET prerequisite_fr = '' WHERE prerequisite_fr IS NULL")
        
        # Now alter columns
        batch_op.alter_column('description_en',
                            existing_type=sa.Text(),
                            nullable=False,
                            server_default='')
        batch_op.alter_column('description_fr',
                            existing_type=sa.Text(),
                            nullable=False,
                            server_default='')
        batch_op.alter_column('prerequisite_en',
                            existing_type=sa.String(255),
                            nullable=False,
                            server_default='')
        batch_op.alter_column('prerequisite_fr',
                            existing_type=sa.String(255),
                            nullable=False,
                            server_default='')
        
        # Add check constraints and indexes
        batch_op.create_check_constraint(
            'check_course_titles',
            'title_en != \'\' AND title_fr != \'\''
        )
        batch_op.create_index('idx_course_code', ['code'])

    # Add constraints for overall_expectations
    with op.batch_alter_table('overall_expectations') as batch_op:
        batch_op.alter_column('description_en',
                            existing_type=sa.Text(),
                            nullable=False,
                            server_default='')
        batch_op.alter_column('description_fr',
                            existing_type=sa.Text(),
                            nullable=False,
                            server_default='')
        batch_op.create_check_constraint(
            'check_overall_descriptions',
            'description_en != \'\' AND description_fr != \'\''
        )
        batch_op.create_index('idx_overall_code', ['code'])
        batch_op.create_index('idx_overall_strand', ['strand_id', 'code'])

    # Add constraints for specific_expectations
    with op.batch_alter_table('specific_expectations') as batch_op:
        batch_op.alter_column('description_en',
                            existing_type=sa.Text(),
                            nullable=False,
                            server_default='')
        batch_op.alter_column('description_fr',
                            existing_type=sa.Text(),
                            nullable=False,
                            server_default='')
        batch_op.create_check_constraint(
            'check_specific_descriptions',
            'description_en != \'\' AND description_fr != \'\''
        )
        batch_op.create_index('idx_specific_code', ['code'])
        batch_op.create_index('idx_specific_overall', ['overall_expectation_id', 'code'])

def downgrade():
    # Remove constraints and indexes in reverse order
    with op.batch_alter_table('specific_expectations') as batch_op:
        batch_op.drop_constraint('check_specific_descriptions')
        batch_op.drop_index('idx_specific_code')
        batch_op.drop_index('idx_specific_overall')
        batch_op.alter_column('description_en', nullable=True)
        batch_op.alter_column('description_fr', nullable=True)

    with op.batch_alter_table('overall_expectations') as batch_op:
        batch_op.drop_constraint('check_overall_descriptions')
        batch_op.drop_index('idx_overall_code')
        batch_op.drop_index('idx_overall_strand')
        batch_op.alter_column('description_en', nullable=True)
        batch_op.alter_column('description_fr', nullable=True)

    with op.batch_alter_table('courses') as batch_op:
        batch_op.drop_constraint('check_course_titles')
        batch_op.drop_index('idx_course_code')
        batch_op.alter_column('description_en', nullable=True)
        batch_op.alter_column('description_fr', nullable=True)
        batch_op.alter_column('prerequisite_en', nullable=True)
        batch_op.alter_column('prerequisite_fr', nullable=True)
