"""
Script to update French titles for strands A and D
"""
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import Strand

def update_strand_titles():
    """Update French titles for strands A and D"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        with app.app_context():
            # Update strand A title
            strand_a = Strand.query.filter_by(code='A').first()
            if strand_a:
                strand_a.title_fr = "Environnement informatique de travail"
                logger.info(f"Updated strand A title to: {strand_a.title_fr}")

            # Update strand D title
            strand_d = Strand.query.filter_by(code='d').first()  # Note: case sensitive, using lowercase 'd'
            if strand_d:
                strand_d.title_fr = "Enjeux sociétaux et perspectives professionnelles"
                logger.info(f"Updated strand D title to: {strand_d.title_fr}")

            db.session.commit()
            logger.info("Database updates completed successfully")

            # Verify updates
            logger.info("\nVerification Results:")
            for strand in Strand.query.order_by(Strand.code).all():
                logger.info(f"Strand {strand.code} title (FR): {strand.title_fr}")

            return True

    except Exception as e:
        logger.error(f"Error updating strand titles: {str(e)}")
        db.session.rollback()
        return False

if __name__ == '__main__':
    update_strand_titles()