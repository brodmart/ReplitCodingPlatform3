"""
Script to create curriculum database tables using Flask-SQLAlchemy
"""
import os
import sys
import logging

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting database table creation...")

        # Initialize database tables within app context
        with app.app_context():
            # First check if tables already exist
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            logger.info(f"Existing tables: {existing_tables}")

            # Create tables
            db.create_all()

            # Verify tables were created
            new_tables = db.inspect(db.engine).get_table_names()
            logger.info(f"Tables after creation: {new_tables}")

            # Verify specific curriculum tables
            required_tables = ['courses', 'strands', 'overall_expectations', 'specific_expectations']
            missing_tables = [table for table in required_tables if table not in new_tables]

            if missing_tables:
                raise Exception(f"Failed to create tables: {missing_tables}")

            logger.info("Database tables created successfully!")

    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()