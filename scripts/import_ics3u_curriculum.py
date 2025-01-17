"""
Script to import ICS3U curriculum data into the database from the provided French curriculum document
"""
import os
import sys
import logging

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from utils.curriculum_importer import CurriculumImporter
from app.models import Course, Strand # Assuming these models exist


def main():
    # Set up logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting ICS3U curriculum import...")

        # Initialize database connection within app context
        with app.app_context():
            # Read ICS3U curriculum content from file
            curriculum_file = 'attached_assets/Pasted-Introduction-au-g-nie-e-informatique-11-ann-e-cours-pr-universitaire-ICS3U-Ce-cours-initi-1737143859140.txt'
            logger.info(f"Reading curriculum from {curriculum_file}")

            with open(curriculum_file, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.info(f"Successfully read {len(content)} characters from file")

            # Import curriculum data
            importer = CurriculumImporter()
            importer.import_curriculum(content)

            # Verify import by checking database
            course = db.session.execute(db.select(Course).filter_by(code='ICS3U')).scalar_one_or_none()
            if course:
                logger.info(f"Successfully imported course {course.code}: {course.title_fr}")
                strand_count = db.session.execute(db.select(db.func.count(Strand.id)).filter_by(course_id=course.id)).scalar()
                logger.info(f"Imported {strand_count} strands")
            else:
                logger.error("Failed to find imported course in database")
                raise Exception("Course import verification failed")

            logger.info("ICS3U curriculum import completed successfully!")

    except Exception as e:
        logger.error(f"Error during curriculum import: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()