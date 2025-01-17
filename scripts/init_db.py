"""
Initialize database tables for curriculum
"""
import os
import sys
from pathlib import Path
from sqlalchemy import inspect

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def init_database():
    """Initialize the database tables"""
    print("Initializing database...")
    with app.app_context():
        # Create all tables
        db.create_all()

        # Verify tables exist
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        expected_tables = ['courses', 'strands', 'overall_expectations', 'specific_expectations']

        # Check if all expected tables exist
        missing_tables = [table for table in expected_tables if table not in tables]
        if missing_tables:
            print("Error: Missing tables:", missing_tables)
            return False

        print("Created tables successfully:", tables)
        return True

if __name__ == "__main__":
    success = init_database()
    if success:
        print("Database initialization completed successfully")
    else:
        print("Database initialization failed")
        sys.exit(1)