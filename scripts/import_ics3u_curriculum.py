"""
Script to import ICS3U curriculum data from the provided French curriculum document
"""
import os
import sys
import logging
from pathlib import Path

# Add parent directory to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from utils.curriculum_importer import CurriculumImporter
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def main():
    # Set up logging with more detail
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting ICS3U curriculum import...")

        # Initialize database connection within app context
        with app.app_context():
            # First verify database tables
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Found tables in database: {tables}")

            required_tables = ['courses', 'strands', 'overall_expectations', 'specific_expectations']
            missing_tables = [table for table in required_tables if table not in tables]

            if missing_tables:
                logger.error(f"Missing required tables: {missing_tables}")
                raise Exception("Database not properly initialized")

            # Create importer instance
            importer = CurriculumImporter()

            # Clear existing data first
            logger.info("Clearing existing ICS3U curriculum data...")
            existing_course = Course.query.filter_by(code='ICS3U').first()
            if existing_course:
                logger.info(f"Found existing course {existing_course.code} - clearing data...")
                db.session.delete(existing_course)
                db.session.commit()

            # Read ICS3U curriculum content from file
            curriculum_file = 'attached_assets/Pasted--Cours-pr-universitaire-11e-ann-eIntroduction-au-g-nie-informatique-11e-ann-e-cours-pr-universitai-1737151455616.txt'
            logger.info(f"Reading curriculum from {curriculum_file}")

            try:
                with open(curriculum_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    logger.info(f"Successfully read {len(content)} characters from file")
                    logger.debug(f"First 500 characters of content: {content[:500]}")
            except Exception as e:
                logger.error(f"Error reading curriculum file: {str(e)}")
                raise

            # Import curriculum data
            importer.import_curriculum(content)

            # Verify import by checking database
            course = Course.query.filter_by(code='ICS3U').first()
            if course:
                logger.info(f"Successfully imported course {course.code}: {course.title_fr}")
                strands = Strand.query.filter_by(course_id=course.id).all()
                logger.info(f"Imported {len(strands)} strands:")
                for strand in strands:
                    logger.info(f"  Strand {strand.code}: {strand.title_fr}")
                    overall_count = OverallExpectation.query.filter_by(strand_id=strand.id).count()
                    specific_count = (
                        db.session.query(SpecificExpectation)
                        .join(OverallExpectation)
                        .filter(OverallExpectation.strand_id == strand.id)
                        .count()
                    )
                    logger.info(f"    Overall expectations: {overall_count}")
                    logger.info(f"    Specific expectations: {specific_count}")
            else:
                logger.error("Failed to find imported course in database")
                raise Exception("Course import verification failed")

            logger.info("ICS3U curriculum import completed successfully!")

    except Exception as e:
        logger.error(f"Error during curriculum import: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()