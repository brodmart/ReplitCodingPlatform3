"""
Script to specifically verify the C2.1 expectation from the curriculum file
"""
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def verify_c21():
    """Verify the C2.1 expectation in database"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        # First verify the curriculum file content
        curriculum_file = project_root / 'attached_assets' / 'ics3u curriculum2.txt'
        with open(curriculum_file, 'r', encoding='utf-8') as f:
            content = f.readlines()

        # Find C2.1 in file
        file_content = {}
        current_strand = None
        current_overall = None

        for line in content:
            line = line.strip()
            if not line:
                continue

            # Look for strand codes (single letter followed by period)
            if len(line) >= 2 and line[0].isalpha() and line[1] == '.':
                current_strand = line[0]
                file_content[current_strand] = {'title': '', 'expectations': {}}

            # Look for C2.1 specifically
            elif line.lower().startswith('c2.1'):
                file_content['file_c21'] = line

        logger.info(f"Found in file: {file_content.get('file_c21', 'Not found')}\n")

        # Now verify database content
        with app.app_context():
            # Get C2.1 and related content
            specific = SpecificExpectation.query.filter(
                SpecificExpectation.code.ilike('C2.1')
            ).first()

            if specific:
                # Get related overall expectation and strand
                overall = OverallExpectation.query.get(specific.overall_expectation_id)
                strand = Strand.query.get(overall.strand_id)

                logger.info("Database Content:")
                logger.info("-" * 50)
                logger.info(f"Strand:")
                logger.info(f"- Code: {strand.code}")
                logger.info(f"- Title (FR): {strand.title_fr or 'Empty'}")
                logger.info(f"- Title (EN): {strand.title_en or 'Empty'}")

                logger.info(f"\nOverall Expectation:")
                logger.info(f"- Code: {overall.code}")
                logger.info(f"- Description (FR): {overall.description_fr or 'Empty'}")
                logger.info(f"- Description (EN): {overall.description_en or 'Empty'}")

                logger.info(f"\nSpecific Expectation:")
                logger.info(f"- Code: {specific.code}")
                logger.info(f"- Description (FR): {specific.description_fr or 'Empty'}")
                logger.info(f"- Description (EN): {specific.description_en or 'Empty'}")

                # Verify completeness
                missing_fields = []
                if not strand.title_fr: missing_fields.append("Strand Title (FR)")
                if not strand.title_en: missing_fields.append("Strand Title (EN)")
                if not overall.description_fr: missing_fields.append("Overall Description (FR)")
                if not overall.description_en: missing_fields.append("Overall Description (EN)")
                if not specific.description_fr: missing_fields.append("Specific Description (FR)")
                if not specific.description_en: missing_fields.append("Specific Description (EN)")

                if missing_fields:
                    logger.warning("\nMissing or Empty Fields:")
                    for field in missing_fields:
                        logger.warning(f"- {field}")
                else:
                    logger.info("\nAll required fields are present")

            else:
                logger.error("\nC2.1 expectation not found in database")
                # List all codes for debugging
                all_codes = SpecificExpectation.query.with_entities(
                    SpecificExpectation.code
                ).all()
                logger.info("\nAvailable codes:")
                for code in all_codes:
                    logger.info(f"- {code[0]}")

            return True

    except Exception as e:
        logger.error(f"Error during verification: {str(e)}", exc_info=True)
        return False

if __name__ == '__main__':
    verify_c21()