"""
Unified database initialization script for the curriculum platform
Combines table creation, admin setup, and basic data initialization
"""
import os
import sys
from pathlib import Path
import logging
from sqlalchemy import inspect

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models import Student, Course, Strand, OverallExpectation, SpecificExpectation

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize database tables and basic data"""
    logger.info("Starting database initialization...")
    
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            logger.info("Created database tables successfully")
            
            # Verify tables exist
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            expected_tables = [
                'student', 'code_submission', 'coding_activity',
                'student_progress', 'shared_code', 'audit_log',
                'achievement', 'student_achievement',
                'courses', 'strands', 'overall_expectations', 
                'specific_expectations'
            ]
            
            # Check if all expected tables exist
            missing_tables = [table for table in expected_tables if table not in tables]
            if missing_tables:
                logger.error("Missing tables: %s", missing_tables)
                return False
                
            # Create admin user if it doesn't exist
            admin = Student.query.filter_by(username='admin').first()
            if not admin:
                admin = Student(
                    username='admin',
                    is_admin=True,
                    failed_login_attempts=0
                )
                success, message = admin.set_password('admin123')
                if not success:
                    logger.error("Failed to set admin password: %s", message)
                    return False
                    
                db.session.add(admin)
                db.session.commit()
                logger.info("Created admin user successfully")
            
            logger.info("Database initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error("Database initialization failed: %s", str(e))
            db.session.rollback()
            return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
