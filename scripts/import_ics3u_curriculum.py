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
    encoding = None
    try:
        with open(file_path, 'rb') as file:
            raw_data = file.read()
            if not raw_data:
                raise ValueError(f"File is empty: {file_path}")
            result = chardet.detect(raw_data)
            if not result or not result['encoding']:
                raise ValueError(f"Could not detect encoding for file: {file_path}")
            encoding = result['encoding']
            logging.info(f"Detected encoding: {encoding} with confidence: {result['confidence']}")
            return encoding
    except (IOError, OSError) as e:
        logging.error(f"Error reading file {file_path}: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error detecting encoding for {file_path}: {str(e)}")
        raise
    finally:
        if not encoding:
            logging.warning(f"Falling back to UTF-8 encoding for {file_path}")
            return 'utf-8'

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

            # Use the specified curriculum file
            curriculum_file = project_root / 'attached_assets' / 'Le-curriculum-de-lOntario-de-la-10e-a-la-12e-annee-Etudes-informatiques-2008-revise.txt'

            if not curriculum_file.exists():
                logger.error(f"Curriculum file not found: {curriculum_file}")
                raise FileNotFoundError(f"No curriculum file found at {curriculum_file}")

            logger.info(f"Found curriculum file: {curriculum_file}")
            logger.info(f"File size: {curriculum_file.stat().st_size} bytes")

            try:
                # Detect file encoding with fallback
                encoding = detect_encoding(curriculum_file)
                logger.info(f"Using encoding: {encoding}")

                with open(curriculum_file, 'r', encoding=encoding) as f:
                    content = f.read()
                    if not content.strip():
                        raise ValueError(f"File {curriculum_file} is empty after stripping whitespace")

                    logger.info(f"Successfully read file using {encoding} encoding")
                    logger.debug(f"Content preview (first 500 chars): {content[:500]}")

                    try:
                        logger.info(f"Starting import from file: {curriculum_file}")
                        importer.import_curriculum(content)

                        # Verify import by checking database
                        course = Course.query.filter_by(code='ICS3U').first()
                        if course:
                            logger.info(f"Successfully imported course {course.code}: {course.title_fr}")

                            # Log strand details
                            strands = Strand.query.filter_by(course_id=course.id).all()
                            logger.info(f"Imported {len(strands)} strands:")

                            for strand in strands:
                                logger.info(f"  Strand {strand.code}: {strand.title_fr}")

                                # Count expectations
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

                    except Exception as e:
                        logger.error(f"Error during import process: {str(e)}", exc_info=True)
                        db.session.rollback()
                        raise

            except UnicodeDecodeError as e:
                logger.error(f"Unicode decode error with {encoding} encoding: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error reading file: {str(e)}")
                raise

            logger.info("ICS3U curriculum import completed successfully!")

    except Exception as e:
        logger.error(f"Error during curriculum import: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()