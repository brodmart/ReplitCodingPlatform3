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

def get_english_description(code: str) -> tuple:
    """Get English descriptions for curriculum items"""
    descriptions = {
        # Strand descriptions
        'A': ('Programming Concepts and Skills', 'Programming fundamentals and computational thinking'),
        'B': ('Software Development', 'Software design and project management'),
        'C': ('Digital Systems and Security', 'Computer systems and cybersecurity'),
        'D': ('Programming in Society', 'Ethics and emerging technologies'),
        # Overall expectations (examples)
        'A1': ('Programming Fundamentals', 'Apply programming concepts and constructs to create practical applications'),
        'A2': ('Data Types and Program Design', 'Design and create programs using various data types and control structures'),
        'A3': ('Testing and Maintenance', 'Test, debug and maintain computer programs'),
        'B1': ('Software Development Life Cycle', 'Follow standard software development life cycle practices'),
        'B2': ('Project Management', 'Apply project management practices in a software project'),
        'C1': ('Computer Systems', 'Demonstrate understanding of computer system components'),
        'C2': ('Networking and Security', 'Describe networking concepts and implement security measures'),
        'D1': ('Ethical Issues', 'Analyze ethical issues in computer programming'),
        'D2': ('Environmental Impact', 'Assess environmental impacts of computer use'),
    }
    return descriptions.get(code, ('', ''))

def parse_curriculum_line(line: str, next_line: str = None) -> tuple:
    """Parse a curriculum line into code and description."""
    line = line.strip()

    # Skip empty or short lines
    if not line or len(line) < 4:
        return None, None, None

    # Split at first space (format is like "A1.1 description")
    parts = line.split(' ', 1)
    if len(parts) != 2:
        return None, None, None

    code = parts[0].strip()
    description_fr = parts[1].strip()

    # If there's a next line and current description doesn't end with a period
    # and the next line doesn't start with a code pattern, append it
    if next_line and not description_fr.endswith('.') and not (
        next_line.strip() and 
        any(next_line.strip().startswith(f"{l}") for l in ['A', 'B', 'C', 'D'])
    ):
        description_fr += ' ' + next_line.strip()

    # Get English description based on code
    title_en, description_en = get_english_description(code)

    return code, description_fr, description_en

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting ICS3U curriculum import process...")

        with app.app_context():
            # Clear existing data
            Course.query.filter_by(code='ICS3U').delete()
            db.session.commit()

            # Create course
            course = Course(
                code='ICS3U',
                title_fr='Introduction au génie informatique, 11e année',
                title_en='Introduction to Computer Science, Grade 11',
                description_en='This course introduces students to computer science concepts and practices.',
                description_fr='Ce cours initie les élèves aux concepts et aux pratiques de l\'informatique.'
            )
            db.session.add(course)
            db.session.commit()

            # Initialize tracking dictionaries
            strands = {}  # key: strand_code, value: Strand object
            overall_expectations = {}  # key: overall_code, value: OverallExpectation object

            # Define curriculum file path
            curriculum_file = project_root / 'attached_assets' / 'ics3u curriculum2.txt'

            if not curriculum_file.exists():
                logger.error(f"Curriculum file not found: {curriculum_file}")
                raise FileNotFoundError(f"No curriculum file found at {curriculum_file}")

            # Process curriculum content
            with open(curriculum_file, 'r', encoding='utf-8') as f:
                content = f.readlines()

            # Process each line
            for line_num, line in enumerate(content):
                next_line = content[line_num + 1] if line_num < len(content) - 1 else None
                code, description_fr, description_en = parse_curriculum_line(line, next_line)

                if not code:
                    continue

                strand_code = code[0]

                # Create strand if needed
                if strand_code not in strands:
                    title_en, desc_en = get_english_description(strand_code)
                    strand = Strand(
                        course_id=course.id,
                        code=strand_code,
                        title_fr=f'Domaine {strand_code}',  # Default French title
                        title_en=title_en
                    )
                    db.session.add(strand)
                    db.session.commit()
                    strands[strand_code] = strand
                    logger.info(f"Created strand: {strand_code}")

                # Handle overall expectations (e.g., 'A1')
                if len(code) == 2 and code[1].isdigit():
                    title_en, desc_en = get_english_description(code)
                    overall = OverallExpectation(
                        strand_id=strands[strand_code].id,
                        code=code,
                        description_fr=description_fr,
                        description_en=desc_en or description_fr  # Use French if English not available
                    )
                    db.session.add(overall)
                    db.session.commit()
                    overall_expectations[code] = overall
                    logger.info(f"Created overall expectation: {code}")

                # Handle specific expectations (e.g., 'A1.1')
                elif '.' in code:
                    overall_code = code.split('.')[0]
                    if overall_code in overall_expectations:
                        specific = SpecificExpectation(
                            overall_expectation_id=overall_expectations[overall_code].id,
                            code=code,
                            description_fr=description_fr,
                            description_en=description_en or description_fr # Use French description if English not available
                        )
                        db.session.add(specific)
                        db.session.commit()
                        logger.info(f"Created specific expectation: {code}")

            logger.info("Curriculum import completed successfully")

    except Exception as e:
        logger.error(f"Import failed: {str(e)}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    main()