"""
Script to import ICS3U curriculum data from the provided French curriculum document
"""
import os
import sys
import logging
from pathlib import Path
import chardet

# Add parent directory to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from utils.curriculum_importer import CurriculumImporter
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def detect_encoding(file_path):
    """Detect the file encoding using chardet with improved error handling"""
    try:
        with open(file_path, 'rb') as file:
            raw_data = file.read()
            if not raw_data:
                raise ValueError(f"File is empty: {file_path}")
            result = chardet.detect(raw_data)
            if not result or not result['encoding']:
                raise ValueError(f"Could not detect encoding for file: {file_path}")
            return result['encoding']
    except Exception as e:
        logging.error(f"Error detecting encoding for {file_path}: {str(e)}")
        return 'utf-8'  # Default to UTF-8 if detection fails

def main():
    # Set up logging with more detail
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting ICS3U curriculum import process...")

        # Initialize database connection within app context
        with app.app_context():
            # First verify database tables and clear any existing data
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

            # Define curriculum file path
            curriculum_file = project_root / 'attached_assets' / 'ics3u curriculum.txt'

            if not curriculum_file.exists():
                logger.error(f"Curriculum file not found: {curriculum_file}")
                raise FileNotFoundError(f"No curriculum file found at {curriculum_file}")

            logger.info(f"Found curriculum file: {curriculum_file}")

            try:
                # Detect and verify file encoding
                encoding = detect_encoding(curriculum_file)
                logger.info(f"Using encoding: {encoding}")

                # Read and verify file content
                with open(curriculum_file, 'r', encoding=encoding) as f:
                    content = f.read()
                    if not content.strip():
                        raise ValueError(f"File {curriculum_file} is empty after stripping whitespace")

                    logger.info(f"Successfully read file ({len(content)} characters)")
                    logger.debug(f"Content preview: {content[:200]}")

                    # Clear existing data before import
                    importer.clear_existing_data()
                    logger.info("Cleared existing data")

                    # Perform the import
                    importer.import_curriculum(content)
                    logger.info("Import completed, verifying results...")

                    # Verify import results
                    course = Course.query.filter_by(code='ICS3U').first()
                    if not course:
                        raise Exception("Course not found after import")

                    strands = Strand.query.filter_by(course_id=course.id).all()
                    logger.info(f"Found {len(strands)} strands")

                    for strand in strands:
                        overall_exps = OverallExpectation.query.filter_by(strand_id=strand.id).all()
                        specific_count = sum(
                            len(overall.specific_expectations) for overall in overall_exps
                        )
                        logger.info(
                            f"Strand {strand.code}: {len(overall_exps)} overall expectations, "
                            f"{specific_count} specific expectations"
                        )

                    logger.info("Import verification completed successfully")

            except UnicodeDecodeError as e:
                logger.error(f"Unicode decode error with {encoding} encoding: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error during import: {str(e)}")
                raise

    except Exception as e:
        logger.error(f"Fatal error during curriculum import: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()