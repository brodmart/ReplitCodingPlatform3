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

            # Read ICS3U curriculum content from file
            curriculum_files = [
                'attached_assets/Pasted--Introduction-au-g-nie-informatique-11e-ann-e-cours-pr-universitaire-ICS3U-Ce-cours-initie-l--1737160312256.txt',
                'curriculum/ICS3U_curriculum.txt',
                'attached_assets/ICS3U_curriculum.txt'
            ]

            content = None
            for file_path in curriculum_files:
                try:
                    full_path = Path(project_root / file_path)
                    if full_path.exists():
                        logger.info(f"Found curriculum file at: {full_path}")
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            logger.info(f"Successfully read {len(content)} characters from {file_path}")
                            logger.debug(f"First 500 characters of content: {content[:500]}")
                            break
                except Exception as e:
                    logger.warning(f"Could not read file {file_path}: {str(e)}")
                    continue

            if content is None:
                logger.error("Could not find or read any curriculum file")
                logger.error(f"Searched in: {', '.join(str(Path(project_root / f)) for f in curriculum_files)}")
                raise FileNotFoundError("No curriculum file found")

            # Import curriculum data
            try:
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

            except Exception as e:
                logger.error(f"Error during import process: {str(e)}")
                db.session.rollback()
                raise

            logger.info("ICS3U curriculum import completed successfully!")

    except Exception as e:
        logger.error(f"Error during curriculum import: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()