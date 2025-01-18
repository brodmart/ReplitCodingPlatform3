"""
Script to update French descriptions for strand C and overall expectation C2
"""
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def update_french_descriptions():
    """Update French descriptions for strand C and overall expectation C2"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        with app.app_context():
            # Update strand C title
            strand = Strand.query.filter_by(code='c').first()
            if strand:
                strand.title_fr = "Développement de logiciels"
                logger.info(f"Updated strand C title to: {strand.title_fr}")

            # Update overall expectation C2 description
            overall = OverallExpectation.query.filter_by(code='c2').first()
            if overall:
                overall.description_fr = "concevoir des algorithmes répondant aux problèmes donnés"
                logger.info(f"Updated C2 description to: {overall.description_fr}")

            db.session.commit()
            logger.info("Database updates completed successfully")

            # Verify updates
            strand_check = Strand.query.filter_by(code='c').first()
            overall_check = OverallExpectation.query.filter_by(code='c2').first()

            if strand_check and overall_check:
                logger.info("\nVerification Results:")
                logger.info(f"Strand C title (FR): {strand_check.title_fr}")
                logger.info(f"Overall C2 description (FR): {overall_check.description_fr}")

            return True

    except Exception as e:
        logger.error(f"Error updating descriptions: {str(e)}")
        db.session.rollback()
        return False

if __name__ == '__main__':
    update_french_descriptions()