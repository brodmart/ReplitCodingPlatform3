"""
Script to import ICD2O curriculum data into the database
"""
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation
from sqlalchemy import select

def clear_existing_data(course_code: str):
    """Clear existing curriculum data for a given course code"""
    logger = logging.getLogger(__name__)

    try:
        with db.session.begin():
            # Get course ID first
            course = Course.query.filter_by(code=course_code).first()
            if not course:
                logger.info(f"No existing data found for course {course_code}")
                return

            # Get strand IDs for this course
            strand_ids = [row[0] for row in db.session.query(Strand.id).filter_by(course_id=course.id).all()]

            # Get overall expectation IDs for these strands
            overall_ids = [
                row[0] for row in 
                db.session.query(OverallExpectation.id)
                .filter(OverallExpectation.strand_id.in_(strand_ids))
                .all()
            ]

            # Delete in reverse order (child to parent)
            if overall_ids:
                db.session.query(SpecificExpectation).filter(
                    SpecificExpectation.overall_expectation_id.in_(overall_ids)
                ).delete(synchronize_session=False)

            if strand_ids:
                db.session.query(OverallExpectation).filter(
                    OverallExpectation.strand_id.in_(strand_ids)
                ).delete(synchronize_session=False)

            db.session.query(Strand).filter(
                Strand.course_id == course.id
            ).delete(synchronize_session=False)

            db.session.query(Course).filter_by(code=course_code).delete()

            logger.info(f"Successfully cleared existing data for course {course_code}")

    except Exception as e:
        logger.error(f"Error clearing existing data: {str(e)}")
        raise

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting ICD2O curriculum import process...")

        # Initialize database connection within app context
        with app.app_context():
            # Clear existing data
            clear_existing_data('ICD2O')

            # Create new course entry
            course = Course(
                code='ICD2O',
                title_en='Digital Technology and Innovations in the Changing World',
                title_fr='Technologies numériques et innovations dans un monde en évolution'
            )
            db.session.add(course)
            db.session.commit()
            logger.info(f"Created course: {course.code}")

            # Wait for user input to continue with strands, expectations, etc.
            logger.info("Ready to receive curriculum data")

    except Exception as e:
        logger.error(f"Import failed: {str(e)}")
        raise

if __name__ == '__main__':
    main()