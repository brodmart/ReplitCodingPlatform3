"""
Script to import ICS3U curriculum data from the provided French curriculum document
"""
import os
import sys
import logging
from pathlib import Path
from sqlalchemy import text

# Add parent directory to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app import app, db
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def parse_curriculum_line(line: str) -> tuple:
    """Parse a curriculum line into code and description."""
    line = line.strip()
    if not line:
        return None, None

    # Look for pattern: code followed by description
    # Handle both A1 and A1.1 formats
    parts = line.split(' ', 1)
    if len(parts) != 2:
        return None, None

    code = parts[0].strip()
    description = parts[1].strip()

    # Basic validation that code starts with letter and contains number
    if not (code[0].isalpha() and any(c.isdigit() for c in code)):
        return None, None

    return code, description

def main():
    # Set up detailed logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting ICS3U curriculum import process...")

        # Initialize database connection within app context
        with app.app_context():
            # Verify database connection
            try:
                db.session.execute(text('SELECT 1'))
                logger.info("Database connection verified")
            except Exception as e:
                logger.error(f"Database connection failed: {str(e)}")
                raise

            # Define curriculum file path
            curriculum_file = project_root / 'attached_assets' / 'ics3u curriculum2.txt'

            if not curriculum_file.exists():
                logger.error(f"Curriculum file not found: {curriculum_file}")
                raise FileNotFoundError(f"No curriculum file found at {curriculum_file}")

            logger.info(f"Found curriculum file: {curriculum_file}")

            try:
                # Read file content
                with open(curriculum_file, 'r', encoding='utf-8') as f:
                    content = f.readlines()

                # Clear existing ICS3U data
                Course.query.filter_by(code='ICS3U').delete()
                db.session.commit()
                logger.info("Cleared existing ICS3U data")

                # Create course
                course = Course(
                    code='ICS3U',
                    title_fr='Introduction au génie informatique, 11e année',
                    title_en='Introduction to Computer Science, Grade 11'
                )
                db.session.add(course)
                db.session.flush()
                logger.info(f"Created course: {course.code}")

                # Track created objects
                strands = {}
                overall_expectations = {}

                # Process each line
                for line in content:
                    code, description = parse_curriculum_line(line)
                    if not code or not description:
                        continue

                    logger.debug(f"Processing line - Code: {code}, Description: {description[:50]}...")

                    # Extract codes
                    strand_code = code[0]

                    # Create strand if needed
                    if strand_code not in strands:
                        strand = Strand(
                            course_id=course.id,
                            code=strand_code,
                            title_fr='',
                            title_en=''
                        )
                        db.session.add(strand)
                        db.session.flush()
                        strands[strand_code] = strand
                        logger.info(f"Created strand: {strand_code}")

                    # Handle expectations
                    if '.' in code:  # Specific expectation (e.g., A1.1)
                        overall_code = code.split('.')[0]
                        if overall_code in overall_expectations:
                            specific = SpecificExpectation(
                                overall_expectation_id=overall_expectations[overall_code].id,
                                code=code,
                                description_fr=description,
                                description_en=''
                            )
                            db.session.add(specific)
                            logger.debug(f"Created specific expectation: {code}")
                    else:  # Overall expectation (e.g., A1)
                        overall = OverallExpectation(
                            strand_id=strands[strand_code].id,
                            code=code,
                            description_fr=description,
                            description_en=''
                        )
                        db.session.add(overall)
                        db.session.flush()
                        overall_expectations[code] = overall
                        logger.info(f"Created overall expectation: {code}")

                # Final commit
                db.session.commit()
                logger.info("Curriculum import completed successfully")

                # Verify import results
                course_check = Course.query.filter_by(code='ICS3U').first()
                if course_check:
                    strand_count = len(strands)
                    overall_count = len(overall_expectations)
                    specific_count = SpecificExpectation.query.join(
                        OverallExpectation
                    ).join(
                        Strand
                    ).filter(
                        Strand.course_id == course_check.id
                    ).count()

                    logger.info(f"Import statistics:")
                    logger.info(f"- Strands: {strand_count}")
                    logger.info(f"- Overall Expectations: {overall_count}")
                    logger.info(f"- Specific Expectations: {specific_count}")
                else:
                    logger.error("Failed to verify course after import")

            except Exception as e:
                logger.error(f"Error processing curriculum file: {str(e)}")
                db.session.rollback()
                raise

    except Exception as e:
        logger.error(f"Fatal error during curriculum import: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()