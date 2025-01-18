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
from models.curriculum import Course, Strand, OverallExpectation, SpecificExpectation

def parse_curriculum_line(line: str, next_line: str = None) -> tuple:
    """Parse a curriculum line into code and description."""
    line = line.strip()

    # Skip empty or short lines
    if not line or len(line) < 4:
        return None, None

    # Split at first space (format is like "A1.1 description")
    parts = line.split(' ', 1)
    if len(parts) != 2:
        return None, None

    code = parts[0].strip()
    description = parts[1].strip()

    # If there's a next line and current description doesn't end with a period
    # and the next line doesn't start with a code pattern, append it
    if next_line and not description.endswith('.') and not (
        next_line.strip() and 
        any(next_line.strip().startswith(f"{l}") for l in ['A', 'B', 'C', 'D', 'a', 'b', 'c', 'd'])
    ):
        description += ' ' + next_line.strip()

    # Validate code format (should be like A1.1)
    if not (code[0].isalpha() and '.' in code and any(c.isdigit() for c in code)):
        return None, None

    return code, description

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting ICS3U curriculum import process...")

        # Initialize database connection within app context
        with app.app_context():
            # Clear existing data
            SpecificExpectation.query.delete()
            OverallExpectation.query.delete()
            Strand.query.delete()
            Course.query.filter_by(code='ICS3U').delete()
            db.session.commit()

            # Define curriculum file path
            curriculum_file = project_root / 'attached_assets' / 'ics3u curriculum2.txt'

            if not curriculum_file.exists():
                logger.error(f"Curriculum file not found: {curriculum_file}")
                raise FileNotFoundError(f"No curriculum file found at {curriculum_file}")

            logger.info(f"Found curriculum file: {curriculum_file}")

            # Create course
            course = Course(
                code='ICS3U',
                title_fr='Introduction au génie informatique, 11e année',
                title_en='Introduction to Computer Science, Grade 11'
            )
            db.session.add(course)
            db.session.commit()
            logger.info(f"Created course: {course.code}")

            # Initialize tracking dictionaries
            strands = {}  # key: strand_code, value: Strand object
            overall_expectations = {}  # key: overall_code, value: OverallExpectation object

            # Read curriculum content
            with open(curriculum_file, 'r', encoding='utf-8') as f:
                content = f.readlines()

            # Process each line
            for line_num, line in enumerate(content, 1):
                # Get next line if available
                next_line = content[line_num] if line_num < len(content) else None

                code, description = parse_curriculum_line(line, next_line)
                if not code or not description:
                    continue

                logger.debug(f"Line {line_num}: Processing code {code}")

                # Extract components from specific expectation code (e.g., A1.1)
                strand_code = code[0]  # 'A'
                overall_code = code.split('.')[0]  # 'A1'

                # Create strand if needed
                if strand_code not in strands:
                    strand = Strand(
                        course_id=course.id,
                        code=strand_code,
                        title_fr='',
                        title_en=''
                    )
                    db.session.add(strand)
                    db.session.commit()
                    strands[strand_code] = strand
                    logger.info(f"Created strand: {strand_code}")

                # Create overall expectation if needed
                if overall_code not in overall_expectations:
                    overall = OverallExpectation(
                        strand_id=strands[strand_code].id,
                        code=overall_code,
                        description_fr='',
                        description_en=''
                    )
                    db.session.add(overall)
                    db.session.commit()
                    overall_expectations[overall_code] = overall
                    logger.info(f"Created overall expectation: {overall_code}")

                # Create specific expectation
                specific = SpecificExpectation(
                    overall_expectation_id=overall_expectations[overall_code].id,
                    code=code,
                    description_fr=description,
                    description_en=''
                )
                db.session.add(specific)
                db.session.commit()
                logger.info(f"Created specific expectation: {code}")

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

                logger.info("Import statistics:")
                logger.info(f"- Strands: {strand_count}")
                logger.info(f"- Overall Expectations: {overall_count}")
                logger.info(f"- Specific Expectations: {specific_count}")
            else:
                logger.error("Failed to verify course after import")

    except Exception as e:
        logger.error(f"Fatal error during curriculum import: {str(e)}", exc_info=True)
        db.session.rollback()
        sys.exit(1)

if __name__ == '__main__':
    main()