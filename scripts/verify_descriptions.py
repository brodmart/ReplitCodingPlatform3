"""
Script to verify the completeness of curriculum expectation descriptions
Non-destructive - only reads from database, no modifications
"""
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import SpecificExpectation, OverallExpectation, Strand

def verify_descriptions():
    """Verify all expectation descriptions for completeness"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        with app.app_context():
            # Get all expectations ordered by code
            expectations = SpecificExpectation.query.join(
                OverallExpectation
            ).join(
                Strand
            ).order_by(
                Strand.code, 
                OverallExpectation.code, 
                SpecificExpectation.code
            ).all()

            logger.info("\nVerifying expectation descriptions:")
            logger.info("-" * 50)

            for expectation in expectations:
                desc = expectation.description_fr
                # Check for potential incomplete descriptions
                if desc and (
                    not desc.endswith('.') or  # No period at end
                    len(desc) < 20 or          # Suspiciously short
                    desc.endswith(',') or      # Ends with comma
                    desc.endswith(' ')         # Ends with space
                ):
                    logger.warning(f"Expectation {expectation.code} may have incomplete description:")
                    logger.warning(f"Current description: {desc}")
                else:
                    logger.info(f"Expectation {expectation.code} description looks complete")

    except Exception as e:
        logger.error(f"Error verifying descriptions: {str(e)}")
        return False

    return True

if __name__ == '__main__':
    verify_descriptions()
