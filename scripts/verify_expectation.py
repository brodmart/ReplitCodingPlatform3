"""
Script to verify specific curriculum expectations in the database
"""
import os
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def verify_expectation(code: str):
    """Verify a specific expectation in the database"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        with app.app_context():
            # Case insensitive query for the specific expectation
            specific = SpecificExpectation.query.filter(
                db.func.lower(SpecificExpectation.code) == code.lower()
            ).first()

            if specific:
                # Get the related overall expectation and strand
                overall = OverallExpectation.query.get(specific.overall_expectation_id)
                strand = Strand.query.get(overall.strand_id)

                logger.info(f"\nExpectation Details for {code}:")
                logger.info("-" * 50)
                logger.info(f"Code: {specific.code}")
                logger.info(f"Description (FR): {specific.description_fr}")
                logger.info(f"Overall Expectation: {overall.code}")
                logger.info(f"Strand: {strand.code}")
                return True
            else:
                logger.error(f"Expectation {code} not found in database")
                # List similar codes to help debugging
                all_codes = SpecificExpectation.query.with_entities(SpecificExpectation.code).all()
                if all_codes:
                    logger.info("Available codes in database:")
                    for code_tuple in all_codes:
                        logger.info(f"- {code_tuple[0]}")
                return False

    except Exception as e:
        logger.error(f"Error verifying expectation: {str(e)}")
        return False

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python verify_expectation.py <expectation_code>")
        print("Example: python verify_expectation.py C2.1")
        sys.exit(1)

    expectation_code = sys.argv[1]  
    verify_expectation(expectation_code)