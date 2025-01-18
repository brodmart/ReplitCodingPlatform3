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
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation
from utils.curriculum_importer import CurriculumImporter

def main():
    # Set up detailed logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting ICS3U curriculum import process...")

        # Initialize database connection within app context
        with app.app_context():
            # First verify database connection
            try:
                db.session.execute('SELECT 1')
                logger.info("Database connection verified")
            except Exception as e:
                logger.error(f"Database connection failed: {str(e)}")
                raise

            # Create importer instance
            importer = CurriculumImporter()

            # Define curriculum file path
            curriculum_file = project_root / 'attached_assets' / 'ics3u curriculum.txt'

            if not curriculum_file.exists():
                logger.error(f"Curriculum file not found: {curriculum_file}")
                raise FileNotFoundError(f"No curriculum file found at {curriculum_file}")

            logger.info(f"Found curriculum file: {curriculum_file}")

            try:
                # Read and verify file content
                with open(curriculum_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        raise ValueError(f"File {curriculum_file} is empty after stripping whitespace")

                    logger.info(f"Successfully read file ({len(content)} characters)")
                    # Log a preview of the content for debugging
                    logger.debug(f"Content preview:\n{content[:500]}...")

                    # Clear existing data with proper error handling
                    try:
                        importer.clear_existing_data()
                        logger.info("Successfully cleared existing data")
                    except Exception as e:
                        logger.error(f"Error clearing existing data: {str(e)}")
                        raise

                    # Perform the import with detailed logging
                    try:
                        importer.import_curriculum(content)
                        logger.info("Import completed successfully")
                    except Exception as e:
                        logger.error(f"Error during curriculum import: {str(e)}")
                        raise

                    # Verify import results
                    course = Course.query.filter_by(code='ICS3U').first()
                    if not course:
                        raise Exception("Course not found after import")

                    strands = Strand.query.filter_by(course_id=course.id).all()
                    logger.info(f"Imported {len(strands)} strands")

                    for strand in strands:
                        overall_exps = OverallExpectation.query.filter_by(strand_id=strand.id).all()
                        specific_count = sum(
                            len(overall.specific_expectations) for overall in overall_exps
                        )
                        logger.info(
                            f"Strand {strand.code}: {len(overall_exps)} overall expectations, "
                            f"{specific_count} specific expectations"
                        )

            except Exception as e:
                logger.error(f"Error processing curriculum file: {str(e)}")
                raise

    except Exception as e:
        logger.error(f"Fatal error during curriculum import: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()