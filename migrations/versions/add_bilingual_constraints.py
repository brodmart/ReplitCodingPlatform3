"""Add bilingual constraints and indexes

Revision ID: add_bilingual_constraints
Revises: 
Create Date: 2025-01-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic
revision = 'add_bilingual_constraints'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add server_default for existing columns
    with op.batch_alter_table('courses') as batch_op:
        batch_op.alter_column('title_en', server_default='')
        batch_op.alter_column('title_fr', server_default='')
        batch_op.alter_column('description_en', server_default='')
        batch_op.alter_column('description_fr', server_default='')
        batch_op.alter_column('prerequisite_en', server_default='')
        batch_op.alter_column('prerequisite_fr', server_default='')
        batch_op.create_check_constraint(
            'check_course_titles', 
            'title_en != "" AND title_fr != ""'
        )
        batch_op.create_index('idx_course_code', ['code'])

    with op.batch_alter_table('strands') as batch_op:
        batch_op.alter_column('title_en', server_default='')
        batch_op.alter_column('title_fr', server_default='')
        batch_op.create_check_constraint(
            'check_strand_titles',
            'title_en != "" AND title_fr != ""'
        )
        batch_op.create_index('idx_strand_code', ['code'])
        batch_op.create_index('idx_strand_course', ['course_id', 'code'])

    with op.batch_alter_table('overall_expectations') as batch_op:
        batch_op.alter_column('description_en', server_default='')
        batch_op.alter_column('description_fr', server_default='')
        batch_op.create_check_constraint(
            'check_overall_descriptions',
            'description_en != "" AND description_fr != ""'
        )
        batch_op.create_index('idx_overall_code', ['code'])
        batch_op.create_index('idx_overall_strand', ['strand_id', 'code'])

    with op.batch_alter_table('specific_expectations') as batch_op:
        batch_op.alter_column('description_en', server_default='')
        batch_op.alter_column('description_fr', server_default='')
        batch_op.create_check_constraint(
            'check_specific_descriptions',
            'description_en != "" AND description_fr != ""'
        )
        batch_op.create_index('idx_specific_code', ['code'])
        batch_op.create_index('idx_specific_overall', ['overall_expectation_id', 'code'])

def downgrade():
    # Remove constraints and indexes
    with op.batch_alter_table('courses') as batch_op:
        batch_op.drop_constraint('check_course_titles')
        batch_op.drop_index('idx_course_code')
        
    with op.batch_alter_table('strands') as batch_op:
        batch_op.drop_constraint('check_strand_titles')
        batch_op.drop_index('idx_strand_code')
        batch_op.drop_index('idx_strand_course')
        
    with op.batch_alter_table('overall_expectations') as batch_op:
        batch_op.drop_constraint('check_overall_descriptions')
        batch_op.drop_index('idx_overall_code')
        batch_op.drop_index('idx_overall_strand')
        
    with op.batch_alter_table('specific_expectations') as batch_op:
        batch_op.drop_constraint('check_specific_descriptions')
        batch_op.drop_index('idx_specific_code')
        batch_op.drop_index('idx_specific_overall')
