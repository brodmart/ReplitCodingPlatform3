"""
Script to update overall expectations with French descriptions from ics3u attentes.txt
"""
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation

def update_overall_expectations():
    """Update overall expectations with French descriptions"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        # Read overall expectations file
        expectations_file = project_root / 'attached_assets' / 'ics3u attentes.txt'
        with open(expectations_file, 'r', encoding='utf-8') as f:
            content = f.readlines()

        # Parse overall expectations
        overall_descriptions = {}
        for line in content:
            line = line.strip()
            if not line:
                continue

            # Look for overall expectations (format: "A1. description")
            parts = line.split('. ', 1)
            if len(parts) == 2 and len(parts[0]) == 2:
                code = parts[0].upper()  # Convert to uppercase for consistency
                description = parts[1].strip()
                if description:  # Only store if we have a description
                    overall_descriptions[code] = description
                    logger.debug(f"Found overall expectation {code}: {description}")

        logger.info(f"Found {len(overall_descriptions)} overall expectations")

        # Update database
        with app.app_context():
            update_count = 0
            for code, description in overall_descriptions.items():
                overall = OverallExpectation.query.filter(
                    db.func.upper(OverallExpectation.code) == code
                ).first()

                if overall:
                    overall.description_fr = description
                    update_count += 1
                    logger.info(f"Updated {code}: {description}")
                else:
                    logger.warning(f"Could not find overall expectation {code} in database")

            db.session.commit()
            logger.info(f"Updated {update_count} overall expectations")

            # Verify updates
            logger.info("\nVerification Results:")
            for strand_code in ['A', 'B', 'C', 'D']:
                strand = Strand.query.filter_by(code=strand_code).first()
                if strand:
                    overalls = OverallExpectation.query.filter_by(strand_id=strand.id).all()
                    logger.info(f"\nStrand {strand_code}:")
                    for overall in overalls:
                        logger.info(f"- {overall.code}: {overall.description_fr}")

            return True

    except Exception as e:
        logger.error(f"Error updating overall expectations: {str(e)}")
        db.session.rollback()
        return False

if __name__ == '__main__':
    update_overall_expectations()
